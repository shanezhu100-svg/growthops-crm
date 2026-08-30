from pathlib import Path
import hashlib
import os
import re
import time
import urllib.parse
import urllib.request

from build_http_redirect_guard import NO_REDIRECT_OPENER, RedirectDenied

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
CSS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css'
CSS_SHA256 = '5ceaaba22d75b58e04150311f596306562a3e595e27ed4b1dfa451b82dda9e50'
CSS_SIZE = 103009
DOWNLOAD_ATTEMPTS = 3
EXPECTED_FONTS = {
    'fa-brands-400.ttf': ('e28096fa75a96ac77020155ea3a6dd7312983e84115366d4cf49a0c312ec6d51', 209128),
    'fa-brands-400.woff2': ('232c6f6a7678304f9efaa26f30b1610debc2ba9f4cd636b5e6751c8d73761b92', 117852),
    'fa-regular-400.ttf': ('9174757efc83e072436e873c22be1663d3c103b0a16d7fb73569af4918d4d351', 67860),
    'fa-regular-400.woff2': ('c27da6f833431da5aa295c44540bfac0fd8270ba6a3c4346427006d8a7b34b76', 25392),
    'fa-solid-900.ttf': ('b4990d0d0c5f5d38d62e936eea120674e584c7eea8dcee38a975c0cf9a37539b', 420332),
    'fa-solid-900.woff2': ('ae17c16afbea216707b2203ea1cf9bdb45b9bfe47d0f4ae3258ddbc6294dd02f', 156400),
    'fa-v4compatibility.ttf': ('ff8f525fb050c5d24519ccc8f5723d85b2e51edd3f9bc6548af55aebadd4f269', 10832),
    'fa-v4compatibility.woff2': ('c7a869faca299d15be10a01f19d0765a7c4d46d8922d9b9317235c1e4a6f0982', 4792),
}
OUT_ROOT = DIST / 'vendor' / 'fontawesome'
CSS_OUT = OUT_ROOT / 'css' / 'all.min.css'
FONT_OUT = OUT_ROOT / 'webfonts'


def fail(message: str) -> None:
    raise SystemExit('FONTAWESOME_STATIC_FINALIZE_FAILED: ' + message)


def fetch_exact(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail('source URL is not an exact HTTPS resource: ' + url)
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={'User-Agent': 'growthops-crm-build/1'})
        try:
            with NO_REDIRECT_OPENER.open(request, timeout=90) as response:
                return response.read()
        except RedirectDenied as exc:
            fail(f'unexpected redirect denied before follow: status={exc.code}')
        except Exception as exc:
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
                continue
            fail(f'download failed after {DOWNLOAD_ATTEMPTS} attempts: {type(exc).__name__}')
    fail('download retry loop exited unexpectedly')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, path)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
external_tag = f'<link rel="stylesheet" href="{CSS_URL}" />'
local_tag = '<link rel="stylesheet" href="/vendor/fontawesome/css/all.min.css" />'
if html.count(external_tag) != 1:
    fail(f'expected external Font Awesome tag exactly once, found {html.count(external_tag)}')

css_bytes = fetch_exact(CSS_URL)
css_actual = sha256(css_bytes)
if css_actual != CSS_SHA256 or len(css_bytes) != CSS_SIZE:
    fail(f'CSS drift; expected={CSS_SHA256}/{CSS_SIZE}; actual={css_actual}/{len(css_bytes)}')
css = css_bytes.decode('utf-8')
if 'Font Awesome Free' not in css or '@font-face' not in css:
    fail('CSS identity markers missing')
if '@import' in css:
    fail('Font Awesome CSS unexpectedly imports another stylesheet')

refs = sorted(set(re.findall(r'url\((?:["\']?)(\.\./webfonts/[^)"\']+)(?:["\']?)\)', css)))
ref_names = [relative.split('/')[-1] for relative in refs]
if ref_names != sorted(EXPECTED_FONTS):
    fail('CSS webfont inventory drift: ' + ','.join(ref_names))

font_bytes = {}
for name in ref_names:
    if not re.fullmatch(r'[A-Za-z0-9._-]+\.(?:woff2|ttf)', name):
        fail('unexpected webfont filename: ' + name)
    url = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/webfonts/' + name
    data = fetch_exact(url)
    actual = sha256(data)
    expected_sha, expected_size = EXPECTED_FONTS[name]
    if actual != expected_sha or len(data) != expected_size:
        fail(f'webfont drift {name}; expected={expected_sha}/{expected_size}; actual={actual}/{len(data)}')
    font_bytes[name] = data

# Only after every network input has passed the complete digest inventory do we
# write deployment output or rewrite the page.
atomic_write(CSS_OUT, css_bytes)
for name, data in font_bytes.items():
    atomic_write(FONT_OUT / name, data)
html = html.replace(external_tag, local_tag, 1)
INDEX.write_text(html, encoding='utf-8')

if html.count(local_tag) != 1 or CSS_URL in html:
    fail('same-origin stylesheet rewrite did not complete exactly once')
if sha256(CSS_OUT.read_bytes()) != CSS_SHA256:
    fail('written CSS digest changed')
for name, (expected_sha, _) in EXPECTED_FONTS.items():
    if sha256((FONT_OUT / name).read_bytes()) != expected_sha:
        fail('written webfont digest changed: ' + name)

print(
    'FONTAWESOME_STATIC_FINALIZE_OK: version=6.5.2; '
    f'css={CSS_SHA256}/{CSS_SIZE}B; webfonts={len(EXPECTED_FONTS)}; '
    f'redirects=pre-follow-denied; download-attempts<={DOWNLOAD_ATTEMPTS}; '
    'output=/vendor/fontawesome; browser-cdnjs-fontawesome=removed'
)
