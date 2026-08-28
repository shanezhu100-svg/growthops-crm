from pathlib import Path
import hashlib
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
CSS_SHA256 = '__PROBE__'
EXPECTED_WEIGHTS = (400, 500, 600, 700, 800)
EXPECTED_SUBSETS = ('latin-ext', 'latin')
EXPECTED_FONTS = {}
OUT_ROOT = DIST / 'vendor' / 'inter'


def fail(message: str) -> None:
    raise SystemExit('INTER_STATIC_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_exact(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment:
        fail('source URL is not an exact HTTPS resource: ' + url)
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': USER_AGENT,
            'Accept': 'text/css,*/*;q=0.1' if parsed.netloc == 'fonts.googleapis.com' else '*/*',
        },
    )
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


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
if html.count(IMPORT) != 1:
    fail(f'expected Google Fonts Inter import exactly once, found {html.count(IMPORT)}')

css_bytes = fetch_exact(CSS_URL)
css_actual = sha256(css_bytes)
css = css_bytes.decode('utf-8')
if 'font-family: \'Inter\'' not in css and 'font-family: "Inter"' not in css:
    fail('Inter identity marker missing from Google Fonts CSS')

blocks = re.findall(r'/\*\s*([^*]+?)\s*\*/\s*@font-face\s*\{(.*?)\}', css, flags=re.S)
selected = {}
for subset, body in blocks:
    subset = subset.strip()
    if subset not in EXPECTED_SUBSETS:
        continue
    weight_match = re.search(r'font-weight:\s*(\d+)', body)
    url_match = re.search(r'src:\s*url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)\s*format\([\'\"]woff2[\'\"]\)', body)
    range_match = re.search(r'unicode-range:\s*([^;]+);', body)
    if not weight_match or not url_match or not range_match:
        fail(f'could not parse {subset} Inter font-face block')
    weight = int(weight_match.group(1))
    if weight not in EXPECTED_WEIGHTS:
        continue
    key = f'{weight}-{subset}'
    if key in selected:
        fail('duplicate font-face key: ' + key)
    selected[key] = {
        'url': url_match.group(1),
        'unicode_range': range_match.group(1).strip(),
    }

expected_keys = {f'{weight}-{subset}' for weight in EXPECTED_WEIGHTS for subset in EXPECTED_SUBSETS}
if set(selected) != expected_keys:
    fail('Inter latin/latin-ext inventory drift: ' + ','.join(sorted(selected)))

font_results = {}
for key in sorted(selected):
    data = fetch_exact(selected[key]['url'])
    if len(data) < 4_000:
        fail(f'Inter font unexpectedly small: {key}/{len(data)}B')
    font_results[key] = (sha256(data), len(data), data)

if CSS_SHA256 == '__PROBE__':
    details = [f'css={css_actual}/{len(css_bytes)}B']
    details.extend(f'{key}={font_results[key][0]}/{font_results[key][1]}B' for key in sorted(font_results))
    fail('PIN_REQUIRED: ' + '; '.join(details))

if css_actual != CSS_SHA256:
    fail(f'Google Fonts CSS drift; expected={CSS_SHA256}; actual={css_actual}')
if set(EXPECTED_FONTS) != expected_keys:
    fail('pinned Inter font inventory does not cover expected latin/latin-ext keys')

# Probe mode intentionally stops before any deployment output is written.
# The pinned follow-up implementation will generate same-origin CSS and woff2 files here.
fail('pinned output implementation missing')
