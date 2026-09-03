from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'

EXPECTED_SHA256 = {
    'index.html': '142947f80f8a9617dfe71843538056799e98d2b9e50a701df243011e97f043c2',
    'tailwind.css': '082358f4ff9c6d67ccb8e628ed27669967e15cfa7908f2e4c36a1e89c0a3f7b6',
    'app/app-inline-01.js': '52ade14219e58afb7b9f4535440479add87f8a59a0404e7fe504cfde5f06c53e',
    'app/app-inline-02.js': 'bca2a9f4935004057b74bf975392fe70cd89b6f388e42e1daacea7fa67b9fdae',
    'app/app-inline-03.js': '160664e1f4ae5df168701b52c2876d0e4c26bc067e17a9c58c767eb25a6bdc8b',
    'app/app-style-01.css': '33a4a117d6b9e820b389e09d87a4ccb94242fb043e80ea087f72c17f46861a70',
    'app/app-style-02.css': '01ed16d03067a8879b877440574fbc6d98af53e0909685e1a23271169c149997',
    'app/app-style-03.css': '64bd5db676657f40c7962080ce62f3b74125865c3f084a67ce21d0fc77ed00b6',
    'app/app-style-04.css': '59de39d8388f561c5229cfa39f7d4c5299b34997c21e3c142d9ced067850a11e',
    'vendor/vue-3.5.41.runtime.global.js': '45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088',
    'vendor/vue-3.5.41.renders.js': '732e24b96d4c1a280026d58cb6edb485afbfe6feffb5284df27123360bdb2cc4',
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
    'vendor/inter/inter.css': 'a9173515531a1bb9820b2adce8e7df7a3cb3b4d114894f836c74ed0fdcafc144',
    'vendor/inter/inter-latin.woff2': '3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62',
    'vendor/inter/inter-latin-ext.woff2': '34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956',
    'cloud-adapter.js': '9713943a80008f625000d6fac2440fb9395f9e6e2c1fd09e820a399c5c34379f',
    'cloud-security-hotfix.js': '157c43b5db3f3c79e29895bed720d72dd86bc3ddf110c32bdc833f4a0a5f0fb8',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': '12258783b11b7ddb5193f20abedabc4234731b4f11c3f5f00016f9ae4483cb72',
}

REQUIRED_STATIC_HEADERS = (
    'Content-Security-Policy:', 'X-Frame-Options:', 'X-Content-Type-Options:',
    'Referrer-Policy:', 'Permissions-Policy:', 'Cross-Origin-Opener-Policy:',
    'Cross-Origin-Resource-Policy: same-origin',
    'X-Robots-Tag: noindex, nofollow, noarchive',
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

compiler_asset = DIST / 'vendor' / 'vue-3.5.41.global.js'
if compiler_asset.exists():
    fail('compiler-inclusive Vue asset returned after runtime-only cutover')

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

print(
    'CLOUDFLARE_P1_OUTPUT_PARITY_OK: '
    f'dist=present; key_artifacts={len(EXPECTED_SHA256)}; production_hashes=match; '
    'same-origin-app-js=hash-pinned; same-origin-app-css=hash-pinned; '
    'same-origin-vendor-js=hash-pinned; vue-runtime-only+renders=hash-pinned; vue-compiler=absent; '
    'same-origin-fontawesome=hash-pinned; same-origin-inter=hash-pinned; '
    'corp=same-origin; robots=noindex+nofollow+noarchive; failopen_404=guarded; static_headers=guarded'
)
