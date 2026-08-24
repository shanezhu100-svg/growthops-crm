from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'

# P1 verifier scope is intentionally narrow: Cloudflare output/parity only.
# Application security is already enforced by sh build.sh and its existing tests.
EXPECTED_SHA256 = {
    'index.html': 'a80eb58791d28a09a4d9fee85dc1de8eb0a29d8718fe9e6a5bbe461cd8794271',
    'cloud-adapter.js': '2a5b5da0f94ba66a2b58ed64b923e0167e7723eb7ccccd3c6384dfbeb471a2a6',
    'cloud-security-hotfix.js': 'f2b3f08c9bbabc4e974c859fe6d86396d028f46b43354b6d74572b5efa938194',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': 'b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7',
}

REQUIRED_STATIC_HEADERS = (
    'Content-Security-Policy:',
    'X-Frame-Options:',
    'X-Content-Type-Options:',
    'Referrer-Policy:',
    'Permissions-Policy:',
    'Cross-Origin-Opener-Policy:',
)

FORBIDDEN_404_MARKERS = (
    '<script', '<form', '<iframe', '<object', '<embed', '<link ',
    '/api/crm', 'growthops_supabase', 'sb_secret_', 'fetch(', 'xmlhttprequest',
    'document.cookie', 'localstorage', 'sessionstorage', 'location.', 'window.',
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_FAILED: ' + message)


if not DIST.is_dir():
    fail('dist/ missing; run sh build.sh first')

# Collect every pinned-artifact mismatch before failing so one CI run exposes the
# complete drift set. Missing files remain fail-closed and are reported alongside
# hash mismatches instead of forcing repeated one-at-a-time diagnostic runs.
drift = []
for name, expected in EXPECTED_SHA256.items():
    path = DIST / name
    if not path.is_file():
        drift.append(f'missing dist/{name}')
        continue
    actual = sha256(path)
    if actual != expected:
        drift.append(
            f'dist/{name} hash drift; expected={expected}; actual={actual}'
        )
if drift:
    fail(' | '.join(drift))

# Fail-open defense in depth: Pages must have a top-level static 404 so an
# exhausted Functions allowance cannot turn an unknown /api/* path into the SPA
# shell. The 404 itself must stay inert and contain no application/API material.
not_found = DIST / '404.html'
if not not_found.is_file():
    fail('missing dist/404.html fail-open guard')
not_found_html = not_found.read_text(encoding='utf-8')
not_found_low = not_found_html.lower()
for marker in (
    '<!doctype html>',
    '<title>404 · not found</title>',
    '<h1>404</h1>',
    'the requested resource was not found.',
    'noindex,nofollow,noarchive',
):
    if marker not in not_found_low:
        fail(f'dist/404.html missing inert marker: {marker}')
for marker in FORBIDDEN_404_MARKERS:
    if marker in not_found_low:
        fail(f'dist/404.html contains active/application material: {marker}')
if re.search(r'\b(?:src|href|action)\s*=', not_found_html, flags=re.I):
    fail('dist/404.html contains a network-bearing attribute')

# The generated wildcard _headers policy must cover the 404 just like the CRM
# shell. Keep this check here as the final Cloudflare-specific deployment gate,
# independently of the earlier build-time header tests.
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
    'failopen_404=guarded; static_headers=guarded'
)
