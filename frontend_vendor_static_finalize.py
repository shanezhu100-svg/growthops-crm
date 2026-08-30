from pathlib import Path
import hashlib
import os
import time
import urllib.parse
import urllib.request

from build_http_redirect_guard import NO_REDIRECT_OPENER, RedirectDenied

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
VENDOR_DIR = DIST / 'vendor'
DOWNLOAD_ATTEMPTS = 3

# Browser vendors are fetched only from exact versioned resources, verified against
# CI-probed SHA-256 authority, then copied into same-origin deploy output. A CDN
# byte change therefore fails the build before any page rewrite or deployment.
VENDORS = (
    {
        'name': 'vue',
        'url': 'https://unpkg.com/vue@3.5.41/dist/vue.global.js',
        'sha256': '14625269265de97b5c344b8fcfb7136c0c9ab09f7dbadc909a4967d14eca05fb',
        'output': 'vue-3.5.41.global.js',
        'min_bytes': 500_000,
        'markers': ('vue v3.5.41', 'var Vue ='),
    },
    {
        'name': 'xlsx',
        'url': 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
        'sha256': 'c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99',
        'output': 'xlsx-0.18.5.full.min.js',
        'min_bytes': 800_000,
        'markers': ('XLSX',),
    },
)


def fail(message: str) -> None:
    raise SystemExit('FRONTEND_VENDOR_STATIC_FINALIZE_FAILED: ' + message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
VENDOR_DIR.mkdir(parents=True, exist_ok=True)

downloaded = []
for vendor in VENDORS:
    url = vendor['url']
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail(f"{vendor['name']} source URL is not a fixed HTTPS resource")
    source_tag = f'<script src="{url}"></script>'
    if html.count(source_tag) != 1:
        fail(f"{vendor['name']} expected source tag exactly once, found {html.count(source_tag)}")

    # Retry only transport failures against the same exact versioned URL. The
    # shared opener rejects 30x before urllib can request the Location target.
    # Content-shape, marker, and digest validation remain fail-closed and are never
    # retried as a way to accept different bytes.
    data = None
    last_error = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={'User-Agent': 'growthops-crm-build/1'})
        try:
            with NO_REDIRECT_OPENER.open(request, timeout=90) as response:
                data = response.read()
        except RedirectDenied as exc:
            fail(f"{vendor['name']} unexpected redirect denied before follow: status={exc.code}")
        except Exception as exc:
            last_error = exc
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
                continue
            fail(
                f"{vendor['name']} download failed after {DOWNLOAD_ATTEMPTS} attempts: "
                f"{type(exc).__name__}"
            )
        last_error = None
        break
    if last_error is not None or data is None:
        fail(f"{vendor['name']} download retry loop exited unexpectedly")

    actual = digest(data)
    if len(data) < vendor['min_bytes']:
        fail(f"{vendor['name']} asset unexpectedly small: {len(data)} bytes")
    text = data.decode('utf-8')
    for marker in vendor['markers']:
        if marker not in text:
            fail(f"{vendor['name']} asset missing marker: {marker}")
    if actual != vendor['sha256']:
        fail(f"{vendor['name']} SHA-256 mismatch: expected={vendor['sha256']}; actual={actual}")

    output = VENDOR_DIR / vendor['output']
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, output)
    local_tag = f'<script src="/vendor/{vendor["output"]}"></script>'
    html = html.replace(source_tag, local_tag, 1)
    downloaded.append((vendor, actual, len(data), local_tag))

INDEX.write_text(html, encoding='utf-8')
for vendor, actual, size, local_tag in downloaded:
    if html.count(local_tag) != 1:
        fail(f"{vendor['name']} local script tag not present exactly once")
    if vendor['url'] in html:
        fail(f"{vendor['name']} external runtime URL remains")
    output = VENDOR_DIR / vendor['output']
    if digest(output.read_bytes()) != actual:
        fail(f"{vendor['name']} written asset digest changed")

print(
    'FRONTEND_VENDOR_STATIC_FINALIZE_OK: '
    + '; '.join(f"{v['name']}={sha}/{size}B->/vendor/{v['output']}" for v, sha, size, _ in downloaded)
    + f'; browser-external-js=removed; redirects=pre-follow-denied; download-attempts<={DOWNLOAD_ATTEMPTS}'
)
