from pathlib import Path
import hashlib
import os
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
VENDOR_DIR = DIST / 'vendor'

# Start new dependencies in explicit probe mode. CI downloads the exact versioned
# resource, reports its digest, and refuses to rewrite the page until the digest is
# reviewed and pinned here in a follow-up commit.
VENDORS = (
    {
        'name': 'vue',
        'url': 'https://unpkg.com/vue@3.5.41/dist/vue.global.js',
        'sha256': '__PROBE__',
        'output': 'vue-3.5.41.global.js',
        'min_bytes': 500_000,
        'markers': ('vue v3.5.41', 'var Vue ='),
    },
    {
        'name': 'xlsx',
        'url': 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
        'sha256': '__PROBE__',
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

probe_results = []
downloaded = []
for vendor in VENDORS:
    url = vendor['url']
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail(f"{vendor['name']} source URL is not a fixed HTTPS resource")
    source_tag = f'<script src="{url}"></script>'
    if html.count(source_tag) != 1:
        fail(f"{vendor['name']} expected source tag exactly once, found {html.count(source_tag)}")

    request = urllib.request.Request(url, headers={'User-Agent': 'growthops-crm-build/1'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            final_url = response.geturl()
            if final_url != url:
                fail(f"{vendor['name']} unexpected redirect: {final_url}")
            data = response.read()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"{vendor['name']} download failed: {type(exc).__name__}")

    actual = digest(data)
    if len(data) < vendor['min_bytes']:
        fail(f"{vendor['name']} asset unexpectedly small: {len(data)} bytes")
    text = data.decode('utf-8')
    for marker in vendor['markers']:
        if marker not in text:
            fail(f"{vendor['name']} asset missing marker: {marker}")

    if vendor['sha256'] == '__PROBE__':
        probe_results.append(f"{vendor['name']}={actual}/{len(data)}B")
        continue
    if actual != vendor['sha256']:
        fail(f"{vendor['name']} SHA-256 mismatch: expected={vendor['sha256']}; actual={actual}")

    output = VENDOR_DIR / vendor['output']
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, output)
    local_tag = f'<script src="/vendor/{vendor["output"]}"></script>'
    html = html.replace(source_tag, local_tag, 1)
    downloaded.append((vendor, actual, len(data), local_tag))

if probe_results:
    fail('PIN_REQUIRED: ' + '; '.join(probe_results))

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
    + '; browser-external-js=removed'
)
