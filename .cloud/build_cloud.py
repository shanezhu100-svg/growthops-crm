from pathlib import Path
import base64
import gzip
import hashlib
import subprocess
import sys
import tempfile

EXPECTED_BASE_SHA256 = "03cc5a54183a02f36af86fd11615386d6368522f5f4fb17ed2fd28085041153a"
EXPECTED_CLOUD_SHA256 = "755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], stderr=subprocess.DEVNULL)


def part_paths(commit: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", commit, "app"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return []
    return sorted(
        p.strip() for p in out.splitlines()
        if p.strip().startswith("app/part-") and p.strip().endswith(".txt")
    )


def decode_commit(commit: str) -> bytes | None:
    paths = part_paths(commit)
    if not paths:
        return None
    try:
        encoded = "".join(git_bytes(commit, p).decode("utf-8") for p in paths).strip()
        encoded += "=" * (-len(encoded) % 4)
        return gzip.decompress(base64.b64decode(encoded))
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
            return None
        return target.read_bytes()


def main() -> None:
    patch_files = sorted(Path(".cloud").glob("patch-*.txt"))
    if len(patch_files) != 8:
        raise SystemExit(f"Expected 8 patch chunks, found {len(patch_files)}")
    patch_text = "".join(path.read_text(encoding="utf-8") for path in patch_files)

    commits = subprocess.check_output(
        ["git", "rev-list", "--all", "--reverse"], text=True
    ).splitlines()
    decoded_count = 0
    candidates = []
    matched_base = None
    matched_cloud = None
    matched_commit = None

    for commit in commits:
        base_html = decode_commit(commit)
        if base_html is None:
            continue
        decoded_count += 1
        base_hash = sha256(base_html)
        candidates.append((commit[:12], base_hash, len(base_html), len(part_paths(commit))))

        if base_hash == EXPECTED_BASE_SHA256:
            matched_base = base_html
            matched_commit = commit
            cloud_html = patch_candidate(base_html, patch_text)
            if cloud_html is not None and sha256(cloud_html) == EXPECTED_CLOUD_SHA256:
                matched_cloud = cloud_html
                break

        cloud_html = patch_candidate(base_html, patch_text)
        if cloud_html is not None and sha256(cloud_html) == EXPECTED_CLOUD_SHA256:
            matched_base = base_html
            matched_cloud = cloud_html
            matched_commit = commit
            break

    print(f"Scanned {len(commits)} commits; decoded {decoded_count} historical bundles")
    for row in candidates[-20:]:
        print(f"candidate commit={row[0]} sha256={row[1]} bytes={row[2]} parts={row[3]}")

    if matched_cloud is None:
        if matched_base is not None:
            raise SystemExit(
                "Found the exact base HTML but cloud patch did not produce the expected SHA"
            )
        raise SystemExit(
            "No historical bundle could reproduce the verified cloud build; deployment blocked"
        )

    dist = Path("dist")
    dist.mkdir(exist_ok=True)
    output = dist / "index.html"
    output.write_bytes(matched_cloud)

    final_hash = sha256(matched_cloud)
    if final_hash != EXPECTED_CLOUD_SHA256:
        raise SystemExit(f"Final SHA mismatch: {final_hash}")

    print(f"Historical base selected: {matched_commit}")
    print(f"GrowthOps cloud build verified: {final_hash}")
    print(f"Output size: {len(matched_cloud)} bytes")


if __name__ == "__main__":
    main()
