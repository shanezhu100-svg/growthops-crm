from pathlib import Path
import hashlib
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"
LOCAL_CSS_TAG = '<link rel="stylesheet" href="/vendor/inter/inter.css" />'
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
CSS_SHA256 = 'ccb4927c1e665717c1f91e480fbbad168db8c70373b7ccf7abf2f70131c04de3'
CSS_SIZE = 12355
DOWNLOAD_ATTEMPTS = 3
EXPECTED_WEIGHTS = (400, 500, 600, 700, 800)
EXPECTED_SUBSETS = ('latin-ext', 'latin')
EXPECTED_ASSETS = {
    'latin': ('3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62', 48256, 'inter-latin.woff2'),
    'latin-ext': ('34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956', 85068, 'inter-latin-ext.woff2'),
}
OUT_ROOT = DIST / 'vendor' / 'inter'
CSS_OUT = OUT_ROOT / 'inter.css'


def fail(message: str) -> None:
    raise SystemExit('INTER_STATIC_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_exact(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment:
        fail('source URL is not an exact HTTPS resource: ' + url)
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
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
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
                continue
            fail(f'download failed after {DOWNLOAD_ATTEMPTS} attempts: {type(exc).__name__}')
    fail('download retry loop exited unexpectedly')


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, path)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
if html.count(IMPORT) != 1:
    fail(f'expected Google Fonts Inter import exactly once, found {html.count(IMPORT)}')
if LOCAL_CSS_TAG in html:
    fail('same-origin Inter stylesheet already present before finalizer')

css_bytes = fetch_exact(CSS_URL)
css_actual = sha256(css_bytes)
if css_actual != CSS_SHA256 or len(css_bytes) != CSS_SIZE:
    fail(f'Google Fonts CSS drift; expected={CSS_SHA256}/{CSS_SIZE}; actual={css_actual}/{len(css_bytes)}')
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
    style_match = re.search(r'font-style:\s*([^;]+);', body)
    display_match = re.search(r'font-display:\s*([^;]+);', body)
    url_match = re.search(r'src:\s*url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)\s*format\([\'\"]woff2[\'\"]\)', body)
    range_match = re.search(r'unicode-range:\s*([^;]+);', body)
    if not weight_match or not style_match or not display_match or not url_match or not range_match:
        fail(f'could not parse {subset} Inter font-face block')
    weight = int(weight_match.group(1))
    if weight not in EXPECTED_WEIGHTS:
        continue
    if style_match.group(1).strip() != 'normal' or display_match.group(1).strip() != 'swap':
        fail(f'Inter style/display drift for {weight}-{subset}')
    key = f'{weight}-{subset}'
    if key in selected:
        fail('duplicate font-face key: ' + key)
    selected[key] = {
        'subset': subset,
        'weight': weight,
        'url': url_match.group(1),
        'unicode_range': range_match.group(1).strip(),
    }

expected_keys = {f'{weight}-{subset}' for weight in EXPECTED_WEIGHTS for subset in EXPECTED_SUBSETS}
if set(selected) != expected_keys:
    fail('Inter latin/latin-ext inventory drift: ' + ','.join(sorted(selected)))

# Google currently serves one variable woff2 per subset across all five weights.
# Enforce that exact deduplicated shape so a silent upstream split/merge cannot
# alter the deployment inventory without review.
subset_urls = {}
for subset in EXPECTED_SUBSETS:
    urls = {selected[f'{weight}-{subset}']['url'] for weight in EXPECTED_WEIGHTS}
    if len(urls) != 1:
        fail(f'Inter {subset} no longer resolves to exactly one shared variable font')
    subset_urls[subset] = next(iter(urls))
if len(set(subset_urls.values())) != len(EXPECTED_SUBSETS):
    fail('Inter latin and latin-ext unexpectedly resolve to the same upstream URL')

font_bytes = {}
for subset in EXPECTED_SUBSETS:
    data = fetch_exact(subset_urls[subset])
    expected_sha, expected_size, _ = EXPECTED_ASSETS[subset]
    actual = sha256(data)
    if actual != expected_sha or len(data) != expected_size:
        fail(f'Inter {subset} drift; expected={expected_sha}/{expected_size}; actual={actual}/{len(data)}')
    font_bytes[subset] = data

# Only after every network input has passed its exact digest/size inventory do we
# write deployment output or rewrite the page.
font_face_blocks = []
for weight in EXPECTED_WEIGHTS:
    for subset in EXPECTED_SUBSETS:
        item = selected[f'{weight}-{subset}']
        _, _, filename = EXPECTED_ASSETS[subset]
        font_face_blocks.append(
            f'/* {subset} */\n'
            '@font-face {\n'
            "  font-family: 'Inter';\n"
            '  font-style: normal;\n'
            f'  font-weight: {weight};\n'
            '  font-display: swap;\n'
            f"  src: url('/vendor/inter/{filename}') format('woff2');\n"
            f"  unicode-range: {item['unicode_range']};\n"
            '}\n'
        )
local_css = ('\n'.join(font_face_blocks)).encode('utf-8')
if local_css.count(b'@font-face') != 10:
    fail('generated Inter CSS must contain exactly 10 font-face blocks')
if b'fonts.googleapis.com' in local_css or b'fonts.gstatic.com' in local_css:
    fail('generated Inter CSS contains external Google Fonts URL')

atomic_write(CSS_OUT, local_css)
for subset in EXPECTED_SUBSETS:
    _, _, filename = EXPECTED_ASSETS[subset]
    atomic_write(OUT_ROOT / filename, font_bytes[subset])

html = html.replace(IMPORT, '', 1)
style_anchor = '<style>'
if html.count(style_anchor) < 1:
    fail('no style anchor available for same-origin Inter stylesheet link')
html = html.replace(style_anchor, LOCAL_CSS_TAG + '\n  ' + style_anchor, 1)
INDEX.write_text(html, encoding='utf-8')

if html.count(LOCAL_CSS_TAG) != 1 or CSS_URL in html or 'fonts.googleapis.com' in html or 'fonts.gstatic.com' in html:
    fail('same-origin Inter rewrite did not remove Google Fonts runtime dependency')
if sha256(CSS_OUT.read_bytes()) != sha256(local_css):
    fail('written Inter CSS digest changed')
for subset, (expected_sha, _, filename) in EXPECTED_ASSETS.items():
    if sha256((OUT_ROOT / filename).read_bytes()) != expected_sha:
        fail('written Inter font digest changed: ' + subset)

print(
    'INTER_STATIC_FINALIZE_OK: css-source='
    f'{CSS_SHA256}/{CSS_SIZE}B; weights=400+500+600+700+800; subsets=latin+latin-ext; '
    f'output-css={sha256(local_css)}/{len(local_css)}B; fonts=2-deduplicated; '
    f'download-attempts<={DOWNLOAD_ATTEMPTS}; browser-google-fonts=removed'
)
