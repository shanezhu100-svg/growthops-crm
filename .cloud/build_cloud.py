from pathlib import Path
import base64
import gzip
import hashlib
import subprocess
import tempfile

EXPECTED_BASE_SHA256 = "03cc5a54183a02f36af86fd11615386d6368522f5f4fb17ed2fd28085041153a"
EXPECTED_CLOUD_SHA256 = "755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_encoded(encoded: str) -> bytes:
    encoded = encoded.strip()
    encoded += "=" * (-len(encoded) % 4)
    return gzip.decompress(base64.b64decode(encoded))


def worktree_part_paths() -> list[Path]:
    return sorted(Path("app").glob("part-*.txt"))


def decode_worktree() -> bytes | None:
    paths = worktree_part_paths()
    if not paths:
        return None
    try:
        encoded = "".join(path.read_text(encoding="utf-8") for path in paths)
        return decode_encoded(encoded)
    except Exception as exc:
        print(f"Current bundle decode failed: {exc}")
        return None


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{commit}:{path}"],
        stderr=subprocess.DEVNULL,
    )


def part_paths(commit: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", commit, "--", "app"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return []
    return sorted(
        p.strip()
        for p in out.splitlines()
        if p.strip().startswith("app/part-") and p.strip().endswith(".txt")
    )


def decode_commit(commit: str) -> bytes | None:
    paths = part_paths(commit)
    if not paths:
        return None
    try:
        encoded = "".join(git_bytes(commit, p).decode("utf-8") for p in paths)
        return decode_encoded(encoded)
    except Exception:
        return None


def patch_candidate(base_html: bytes, patch_text: str) -> bytes | None:
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "index.html"
        target.write_bytes(base_html)
        proc = subprocess.run(
            ["patch", "-s", str(target)],
            input=patch_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode != 0:
            print(f"Patch rejected candidate: {proc.stdout.strip()}")
            return None
        return target.read_bytes()


def resolve_cloud_candidate(candidate: bytes, patch_text: str) -> tuple[bytes | None, str]:
    candidate_hash = sha256(candidate)
    if candidate_hash == EXPECTED_CLOUD_SHA256:
        return candidate, "verified current cloud bundle"
    if candidate_hash == EXPECTED_BASE_SHA256:
        patched = patch_candidate(candidate, patch_text)
        if patched is not None and sha256(patched) == EXPECTED_CLOUD_SHA256:
            return patched, "verified current base bundle + cloud patch"
    return None, f"unrecognized bundle sha256={candidate_hash}"


def main() -> None:
    patch_files = sorted(Path(".cloud").glob("patch-*.txt"))
    if len(patch_files) != 8:
        raise SystemExit(f"Expected 8 patch chunks, found {len(patch_files)}")
    patch_text = "".join(path.read_text(encoding="utf-8") for path in patch_files)

    # Prefer the bundle that is actually committed on main. This makes the
    # deployment deterministic and avoids depending on historical git objects.
    current = decode_worktree()
    if current is not None:
        cloud_html, source = resolve_cloud_candidate(current, patch_text)
        print(
            f"Current bundle: parts={len(worktree_part_paths())} "
            f"bytes={len(current)} sha256={sha256(current)}"
        )
        if cloud_html is not None:
            write_verified_output(cloud_html, source)
            return
        print(f"Current bundle not deployable: {source}; trying history fallback")

    # Compatibility fallback for older repository states.
    commits = subprocess.check_output(
        ["git", "rev-list", "--all", "--reverse"], text=True
    ).splitlines()
    decoded_count = 0

    for commit in commits:
        candidate = decode_commit(commit)
        if candidate is None:
            continue
        decoded_count += 1
        cloud_html, source = resolve_cloud_candidate(candidate, patch_text)
        if cloud_html is not None:
            write_verified_output(cloud_html, f"history {commit[:12]}: {source}")
            return

    raise SystemExit(
        f"Deployment blocked: current bundle did not match the verified cloud build, "
        f"and {decoded_count} historical bundles were decoded without a verified match"
    )


def write_verified_output(cloud_html: bytes, source: str) -> None:
    final_hash = sha256(cloud_html)
    if final_hash != EXPECTED_CLOUD_SHA256:
        raise SystemExit(f"Final SHA mismatch: {final_hash}")

    dist = Path("dist")
    dist.mkdir(exist_ok=True)
    output = dist / "index.html"
    output.write_bytes(cloud_html)

    print(f"GrowthOps cloud build verified from {source}")
    print(f"Final sha256: {final_hash}")
    print(f"Output size: {len(cloud_html)} bytes")


if __name__ == "__main__":
    main()
