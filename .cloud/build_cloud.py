from pathlib import Path
import base64, gzip, hashlib, subprocess, tempfile

BASE_SHA = '03cc1429b4423ec5bce11ce614eb29175dbe4994648d3e2f43f36945c563fadc'
FINAL_SHA = '755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    paths = [Path(f'app/part-{i:03d}.txt') for i in range(1, 14)]
    if not all(p.exists() for p in paths):
        raise SystemExit('Missing historical CRM app resource parts')
    parts = [p.read_text(encoding='utf-8').strip() for p in paths]
    if len(parts[7]) == 14999:
        parts[7] = parts[7][:1840] + 'N' + parts[7][1840:]
    if len(parts[11]) == 14999:
        parts[11] = parts[11][:6048] + 'r' + parts[11][6048:]
    base = gzip.decompress(base64.b64decode(''.join(parts)))
    if sha256(base) != BASE_SHA:
        raise SystemExit(f'Historical CRM base SHA mismatch: {sha256(base)}')

    patch_paths = [Path(f'.cloud/patch-{i:03d}.txt') for i in range(1, 9)]
    if not all(p.exists() for p in patch_paths):
        raise SystemExit('Missing CRM cloud patch parts')
    patch_text = ''.join(p.read_text(encoding='utf-8') for p in patch_paths)

    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / 'index.html'
        target.write_bytes(base)
        proc = subprocess.run(
            ['patch', '-s', str(target)],
            input=patch_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode != 0:
            raise SystemExit('CRM cloud patch failed: ' + proc.stdout.strip())
        final = target.read_bytes()

    if sha256(final) != FINAL_SHA:
        raise SystemExit(f'Final CRM SHA mismatch: {sha256(final)}')
    dist = Path('dist')
    dist.mkdir(exist_ok=True)
    (dist / 'index.html').write_bytes(final)
    print(f'GrowthOps CRM verified build: {len(final)} bytes sha256={FINAL_SHA}')


if __name__ == '__main__':
    main()
