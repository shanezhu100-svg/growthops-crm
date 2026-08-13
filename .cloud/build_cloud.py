from pathlib import Path
import base64
import gzip
import hashlib
import subprocess
import sys

BASE_COMMIT = "89bc4b9f84fa5e1bdc18064b74359c01e23b3acb"
EXPECTED_BASE_SHA256 = "03cc5a54183a02f36af86fd11615386d6368522f5f4fb17ed2fd28085041153a"
EXPECTED_CLOUD_SHA256 = "755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f"
PART_COUNT = 13


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_show(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{path}"])


def main() -> None:
    encoded_parts = []
    for number in range(1, PART_COUNT + 1):
        path = f"app/part-{number:03d}.txt"
        encoded_parts.append(git_show(path).decode("utf-8"))

    encoded = "".join(encoded_parts).strip()
    encoded += "=" * (-len(encoded) % 4)
    base_html = gzip.decompress(base64.b64decode(encoded))
    actual_base_sha = sha256(base_html)
    if actual_base_sha != EXPECTED_BASE_SHA256:
        raise SystemExit(
            f"Stable base SHA mismatch: expected {EXPECTED_BASE_SHA256}, got {actual_base_sha}"
        )

    dist = Path("dist")
    dist.mkdir(exist_ok=True)
    output = dist / "index.html"
    output.write_bytes(base_html)

    patch_files = sorted(Path(".cloud").glob("patch-*.txt"))
    if len(patch_files) != 8:
        raise SystemExit(f"Expected 8 patch chunks, found {len(patch_files)}")
    patch_text = "".join(path.read_text(encoding="utf-8") for path in patch_files)

    proc = subprocess.run(
        ["patch", "-s", str(output)],
        input=patch_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        raise SystemExit(f"Cloud patch failed with exit code {proc.returncode}")

    final_html = output.read_bytes()
    actual_cloud_sha = sha256(final_html)
    if actual_cloud_sha != EXPECTED_CLOUD_SHA256:
        raise SystemExit(
            f"Cloud build SHA mismatch: expected {EXPECTED_CLOUD_SHA256}, got {actual_cloud_sha}"
        )

    print(f"GrowthOps cloud build verified: {actual_cloud_sha}")
    print(f"Output size: {len(final_html)} bytes")


if __name__ == "__main__":
    main()
