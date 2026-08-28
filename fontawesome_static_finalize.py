from pathlib import Path
import hashlib
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
CSS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css'
CSS_SHA256 = '__PROBE__'
EXPECTED_FONTS = {}


def fail(message: str) -> None:
    raise SystemExit('FONTAWESOME_STATIC_FINALIZE_FAILED: ' + message)


def fetch_exact(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail('source URL is not an exact HTTPS resource: ' + url)
    request = urllib.request.Request(url, headers={'User-Agent': 'growthops-crm-build/1'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            final_url = response.geturl()
            if final_url != url:
                fail('unexpected redirect: ' + final_url)
            return response.read()
    except SystemExit:
        raise
    except Exception as exc:
        fail('download failed: ' + type(exc).__name__)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
external_tag = f'<link rel="stylesheet" href="{CSS_URL}" />'
if html.count(external_tag) != 1:
    fail(f'expected external Font Awesome tag exactly once, found {html.count(external_tag)}')

css_bytes = fetch_exact(CSS_URL)
if len(css_bytes) < 50_000:
    fail(f'CSS unexpectedly small: {len(css_bytes)} bytes')
css = css_bytes.decode('utf-8')
if 'Font Awesome Free' not in css or '@font-face' not in css:
    fail('CSS identity markers missing')
if '@import' in css:
    fail('Font Awesome CSS unexpectedly imports another stylesheet')

refs = sorted(set(re.findall(r'url\((?:["\']?)(\.\./webfonts/[^)"\']+)(?:["\']?)\)', css)))
if not 1 <= len(refs) <= 16:
    fail(f'unexpected referenced webfont count: {len(refs)}')
font_results = []
for relative in refs:
    name = relative.split('/')[-1]
    if not re.fullmatch(r'[A-Za-z0-9._-]+\.(?:woff2|ttf)', name):
        fail('unexpected webfont filename: ' + name)
    url = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/webfonts/' + name
    data = fetch_exact(url)
    if len(data) < 1_000:
        fail(f'webfont unexpectedly small: {name}/{len(data)}')
    font_results.append((name, sha256(data), len(data)))

css_actual = sha256(css_bytes)
if CSS_SHA256 == '__PROBE__' or not EXPECTED_FONTS:
    print(f'FONTAWESOME_STATIC_PROBE: css={css_actual}/{len(css_bytes)}B; refs={len(font_results)}')
    for name, digest, size in font_results:
        print(f'FONTAWESOME_STATIC_PROBE_FONT: {name}={digest}/{size}B')
    fail('probe mode: review and pin CSS/webfont SHA-256 values before page rewrite')

fail('pinned mode not implemented yet')
