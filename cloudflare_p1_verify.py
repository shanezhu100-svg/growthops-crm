from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'

# P1 verifier scope is intentionally narrow: Cloudflare output/parity only.
# Application security is already enforced by sh build.sh and its existing tests.
EXPECTED_SHA256 = {
    'index.html': '8ed60d6e3c5b1588b6fafff68a9dc9157dc68ba9f0bf5e1e4edb4737d2aa9a66',
    'tailwind.css': '082358f4ff9c6d67ccb8e628ed27669967e15cfa7908f2e4c36a1e89c0a3f7b6',
    'vendor/vue-3.5.41.global.js': '14625269265de97b5c344b8fcfb7136c0c9ab09f7dbadc909a4967d14eca05fb',
    'vendor/xlsx-0.18.5.full.min.js': 'c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99',
    'vendor/fontawesome/css/all.min.css': '5ceaaba22d75b58e04150311f596306562a3e595e27ed4b1dfa451b82dda9e50',
    'vendor/fontawesome/webfonts/fa-brands-400.ttf': 'e28096fa75a96ac77020155ea3a6dd7312983e84115366d4cf49a0c312ec6d51',
    'vendor/fontawesome/webfonts/fa-brands-400.woff2': '232c6f6a7678304f9efaa26f30b1610debc2ba9f4cd636b5e6751c8d73761b92',
    'vendor/fontawesome/webfonts/fa-regular-400.ttf': '9174757efc83e072436e873c22be1663d3c103b0a16d7fb73569af4918d4d351',
    'vendor/fontawesome/webfonts/fa-regular-400.woff2': 'c27da6f833431da5aa295c44540bfac0fd8270ba6a3c4346427006d8a7b34b76',
    'vendor/fontawesome/webfonts/fa-solid-900.ttf': 'b4990d0d0c5f5d38d62e936eea120674e584c7eea8dcee38a975c0cf9a37539b',
    'vendor/fontawesome/webfonts/fa-solid-900.woff2': 'ae17c16afbea216707b2203ea1cf9bdb45b9bfe47d0f4ae3258ddbc6294dd02f',
    'vendor/fontawesome/webfonts/fa-v4compatibility.ttf': 'ff8f525fb050c5d24519ccc8f5723d85b2e51edd3f9bc6548af55aebadd4f269',
    'vendor/fontawesome/webfonts/fa-v4compatibility.woff2': 'c7a869faca299d15be10a01f19d0765a7c4d46d8922d9b9317235c1e4a6f0982',
    'vendor/inter/inter.css': '__PENDING_INTER_CSS_SHA256__',
    'vendor/inter/inter-latin.woff2': '3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62',
    'vendor/inter/inter-latin-ext.woff2': '34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956',
    'cloud-adapter.js': '9713943a80008f625000d6fac2440fb9395f9e6e2c1fd09e820a399c5c34379f',
    'cloud-security-hotfix.js': 'f2b3f08c9bbabc4e974c859fe6d86396d028f46b43354b6d74572b5efa938194',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': 'b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7',
}

REQUIRED_STATIC_HEADERS = (
    'Content-Security-Policy:', 'X-Frame-Options:', 'X-Content-Type-Options:',
    'Referrer-Policy:', 'Permissions-Policy:', 'Cross-Origin-Opener-Policy:',
)
FORBIDDEN_404_MARKERS = (
    '<script', '<form', '<iframe', '<object', '<embed', '<link ', '/api/crm',
    'growthops_supabase', 'sb_secret_', 'fetch(', 'xmlhttprequest', 'document.cookie',
    'localstorage', 'sessionstorage', 'location.', 'window.',
)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fail(message: str) -> None:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_FAILED: ' + message)

if not DIST.is_dir():
    fail('dist/ missing; run sh build.sh first')
drift = []
for name, expected in EXPECTED_SHA256.items():
    path = DIST / name
    if not path.is_file():
        drift.append(f'missing dist/{name}')
        continue
    actual = sha256(path)
    if actual != expected:
        drift.append(f'dist/{name} hash drift; expected={expected}; actual={actual}')
if drift:
    fail(' | '.join(drift))

not_found = DIST / '404.html'
if not not_found.is_file():
    fail('missing dist/404.html fail-open guard')
not_found_html = not_found.read_text(encoding='utf-8')
not_found_low = not_found_html.lower()
for marker in ('<!doctype html>', '<title>404 · not found</title>', '<h1>404</h1>', 'the requested resource was not found.', 'noindex,nofollow,noarchive'):
    if marker not in not_found_low:
        fail(f'dist/404.html missing inert marker: {marker}')
for marker in FORBIDDEN_404_MARKERS:
    if marker in not_found_low:
        fail(f'dist/404.html contains active/application material: {marker}')
if re.search(r'\b(?:src|href|action)\s*=', not_found_html, flags=re.I):
    fail('dist/404.html contains a network-bearing attribute')

headers_path = DIST / '_headers'
if not headers_path.is_file():
    fail('missing dist/_headers')
headers = headers_path.read_text(encoding='utf-8')
if not headers.startswith('/*\n'):
    fail('dist/_headers does not start with the wildcard /* rule')
missing_headers = [name for name in REQUIRED_STATIC_HEADERS if name not in headers]
if missing_headers:
    fail('dist/_headers missing security headers: ' + ', '.join(missing_headers))

print('CLOUDFLARE_P1_OUTPUT_PARITY_OK: ' f'dist=present; key_artifacts={len(EXPECTED_SHA256)}; production_hashes=match; ' 'same-origin-vendor-js=hash-pinned; same-origin-fontawesome=hash-pinned; same-origin-inter=hash-pinned; failopen_404=guarded; static_headers=guarded')
