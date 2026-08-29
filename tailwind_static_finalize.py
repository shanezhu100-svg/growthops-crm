from pathlib import Path
import hashlib
import os
import platform
import stat
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
INPUT = ROOT / 'tailwind.input.css'
OUTPUT = DIST / 'tailwind.css'

VERSION = '3.4.17'
PLAY_URL = f'https://cdn.tailwindcss.com/{VERSION}'
PLAY_TAG = f'<script src="{PLAY_URL}"></script>'
STATIC_TAG = '<link rel="stylesheet" href="/tailwind.css" />'
DOWNLOAD_ATTEMPTS = 3

# Tailwind CSS v3.4.17 standalone release checksums. Keep both common Linux
# architectures fail-closed so CI/hosting cannot silently execute a different
# downloaded binary.
RELEASES = {
    'x86_64': (
        'tailwindcss-linux-x64',
        '7d24f7fa191d2193b78cd5f5a42a6093e14409521908529f42d80b11fde1f1d4',
    ),
    'amd64': (
        'tailwindcss-linux-x64',
        '7d24f7fa191d2193b78cd5f5a42a6093e14409521908529f42d80b11fde1f1d4',
    ),
    'aarch64': (
        'tailwindcss-linux-arm64',
        '69b1378b8133192d7d2feb12a116fa12d035594f58db3eff215879e4ad8cf39b',
    ),
    'arm64': (
        'tailwindcss-linux-arm64',
        '69b1378b8133192d7d2feb12a116fa12d035594f58db3eff215879e4ad8cf39b',
    ),
}


def fail(message: str) -> None:
    raise SystemExit('TAILWIND_STATIC_FINALIZE_FAILED: ' + message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
if not INPUT.is_file():
    fail('tailwind.input.css missing')

machine = platform.machine().lower()
if machine not in RELEASES:
    fail(f'unsupported build architecture: {machine}')
asset_name, expected_sha = RELEASES[machine]
url = f'https://github.com/tailwindlabs/tailwindcss/releases/download/v{VERSION}/{asset_name}'

# Keep the verified tool outside dist/ so it is never shipped to browsers. Reuse
# only when the cached bytes still match the pinned digest. A transient network
# failure may be retried against this same immutable release URL, but digest drift
# is never retried or accepted.
tool = Path(tempfile.gettempdir()) / f'growthops-tailwindcss-v{VERSION}-{asset_name}'
if not tool.is_file() or sha256(tool) != expected_sha:
    tmp = tool.with_suffix('.download')
    last_error = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        tmp.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'growthops-crm-build/1'})
            with urllib.request.urlopen(request, timeout=90) as response, tmp.open('wb') as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            last_error = exc
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
                continue
            fail(
                f'could not download pinned Tailwind CLI after {DOWNLOAD_ATTEMPTS} attempts: '
                f'{type(exc).__name__}'
            )
        actual_sha = sha256(tmp)
        if actual_sha != expected_sha:
            tmp.unlink(missing_ok=True)
            fail(f'Tailwind CLI SHA-256 mismatch: expected={expected_sha}; actual={actual_sha}')
        os.replace(tmp, tool)
        last_error = None
        break
    if last_error is not None:
        fail('pinned Tailwind CLI download retry loop exited unexpectedly')

if sha256(tool) != expected_sha:
    fail('cached Tailwind CLI digest mismatch')
tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

html_before = INDEX.read_text(encoding='utf-8')
if html_before.count(PLAY_TAG) != 1:
    fail(f'expected exactly one pinned Tailwind Play tag, found {html_before.count(PLAY_TAG)}')
if STATIC_TAG in html_before:
    fail('static Tailwind stylesheet tag already exists before finalizer')

# Scan the final post-UI-finalizer HTML/JS payload, then minify a deterministic
# same-origin CSS asset. The readiness gate separately forbids runtime utility-name
# construction that this static scanner could not discover.
try:
    subprocess.run(
        [
            str(tool),
            '-i', str(INPUT),
            '-o', str(OUTPUT),
            '--content', str(INDEX),
            '--minify',
        ],
        cwd=ROOT,
        check=True,
        timeout=120,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
except subprocess.TimeoutExpired:
    fail('Tailwind CLI timed out')
except subprocess.CalledProcessError as exc:
    detail = (exc.stderr or exc.stdout or '').strip().splitlines()
    fail('Tailwind CLI failed' + (': ' + detail[-1][:240] if detail else ''))

if not OUTPUT.is_file():
    fail('dist/tailwind.css was not produced')
css = OUTPUT.read_text(encoding='utf-8')
if len(css.encode('utf-8')) < 4096:
    fail('generated Tailwind CSS unexpectedly small')
for marker in ('.hidden{display:none}', '.flex{display:flex}', '.grid{display:grid}'):
    if marker not in css:
        fail(f'generated Tailwind CSS missing expected utility marker: {marker}')

INDEX.write_text(html_before.replace(PLAY_TAG, STATIC_TAG, 1), encoding='utf-8')
html_after = INDEX.read_text(encoding='utf-8')
if PLAY_URL in html_after or 'https://cdn.tailwindcss.com' in html_after:
    fail('Tailwind Play CDN remains after static replacement')
if html_after.count(STATIC_TAG) != 1:
    fail('static Tailwind stylesheet tag not present exactly once')

print(
    'TAILWIND_STATIC_FINALIZE_OK: '
    f'version={VERSION}; asset={asset_name}; sha256={expected_sha}; '
    f'css_bytes={len(css.encode("utf-8"))}; play_runtime=absent; stylesheet=/tailwind.css; '
    f'download-attempts<={DOWNLOAD_ATTEMPTS}'
)
