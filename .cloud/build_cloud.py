from pathlib import Path
import base64
import gzip
import hashlib
import itertools
import subprocess
import tempfile

EXPECTED_BASE_SHA256 = "03cc5a54183a02f36af86fd11615386d6368522f5f4fb17ed2fd28085041153a"
EXPECTED_CLOUD_SHA256 = "755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_encoded(encoded: str) -> bytes:
    encoded = encoded.strip()
    encoded += "=" * (-len(encoded) % 4)
    return gzip.decompress(base64.b64decode(encoded))


def worktree_part_paths() -> list[Path]:
    return sorted(Path("app").glob("part-*.txt"))


def read_parts(paths: list[Path]) -> list[str]:
    return [path.read_text(encoding="utf-8").strip() for path in paths]


def repair_truncated_chunk_boundaries(parts: list[str]) -> bytes | None:
    # Two historical upload chunks were stored with 14,999 chars instead of
    # 15,000. The original split size makes the missing position deterministic:
    # it is the right edge of those chunks. Enumerate only the missing Base64
    # values and accept a result solely when the known base SHA matches.
    gaps = [i for i, part in enumerate(parts) if len(part) == 14999]
    if not gaps:
        return None
    if len(gaps) > 3:
        print(f"Refusing repair: unexpected number of truncated chunks: {len(gaps)}")
        return None

    print(f"Trying verified boundary repair for chunks: {[i + 1 for i in gaps]}")
    for chars in itertools.product(BASE64_ALPHABET, repeat=len(gaps)):
        repaired = parts.copy()
        for index, char in zip(gaps, chars):
            repaired[index] += char
        try:
            candidate = decode_encoded("".join(repaired))
        except Exception:
            continue
        if sha256(candidate) == EXPECTED_BASE_SHA256:
            print(
                "Recovered exact base bundle; missing boundary chars="
                + ",".join(f"part-{i + 1:03d}:{c}" for i, c in zip(gaps, chars))
            )
            return candidate
    return None


def decode_worktree() -> bytes | None:
    paths = worktree_part_paths()
    if not paths:
        return None
    parts = read_parts(paths)
    try:
        return decode_encoded("".join(parts))
    except Exception as exc:
        print(f"Current bundle decode failed: {exc}")

    repaired = repair_truncated_chunk_boundaries(parts)
    if repaired is not None:
        return repaired
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
        return candidate, "verified cloud bundle"
    if candidate_hash == EXPECTED_BASE_SHA256:
        patched = patch_candidate(candidate, patch_text)
        if patched is not None and sha256(patched) == EXPECTED_CLOUD_SHA256:
            return patched, "verified base bundle + cloud patch"
    return None, f"unrecognized bundle sha256={candidate_hash}"


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


def main() -> None:
    patch_files = sorted(Path(".cloud").glob("patch-*.txt"))
    if len(patch_files) != 8:
        raise SystemExit(f"Expected 8 patch chunks, found {len(patch_files)}")
    patch_text = "".join(path.read_text(encoding="utf-8") for path in patch_files)

    current = decode_worktree()
    if current is None:
        raise SystemExit("Deployment blocked: unable to reconstruct the verified CRM base bundle")

    print(
        f"Base bundle: parts={len(worktree_part_paths())} "
        f"bytes={len(current)} sha256={sha256(current)}"
    )
    cloud_html, source = resolve_cloud_candidate(current, patch_text)
    if cloud_html is None:
        raise SystemExit(f"Deployment blocked: {source}")

    write_verified_output(cloud_html, source)


if __name__ == "__main__":
    main()
