from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / 'dist' / '404.html'
HEADERS = ROOT / 'dist' / '_headers'
BUILD = ROOT / 'build.sh'

if not PAGE.is_file():
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED missing dist/404.html')

html = PAGE.read_text(encoding='utf-8')
headers = HEADERS.read_text(encoding='utf-8') if HEADERS.is_file() else ''
build = BUILD.read_text(encoding='utf-8')
low = html.lower()

required = (
    '<!doctype html>',
    '<title>404 · not found</title>',
    '<h1>404</h1>',
    'the requested resource was not found.',
    'noindex,nofollow,noarchive',
)
missing = [marker for marker in required if marker not in low]
if missing:
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED missing markers: ' + ', '.join(missing))

for forbidden in (
    '<script', '<form', '<iframe', '<object', '<embed', '<link ',
    '/api/crm', 'growthops_supabase', 'sb_secret_', 'fetch(', 'xmlhttprequest',
    'location.', 'window.', 'document.cookie', 'localstorage', 'sessionstorage',
):
    if forbidden in low:
        raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED active/app material present: ' + forbidden)

# No network-bearing attributes. Inline CSS is deliberate and covered by the
# existing static CSP source of truth; there are no scripts or external assets.
if re.search(r'\b(?:src|href|action)\s*=', html, flags=re.I):
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED network-bearing attribute present')

if not headers.startswith('/*\n'):
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED wildcard static security headers missing')
if 'Content-Security-Policy:' not in headers:
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED CSP missing from static headers')

finalize_call = 'python3 cloudflare_failopen_404_finalize.py'
test_call = 'python3 test_cloudflare_failopen_404.py'
if build.count(finalize_call) != 1 or build.count(test_call) != 1:
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED build pipeline not wired exactly once')
if build.index(finalize_call) > build.index(test_call):
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED test runs before generator')
if build.index('python3 cloudflare_headers_finalize.py') > build.index(test_call):
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_TEST_FAILED test runs before static headers')

print('CLOUDFLARE_FAILOPEN_404_TESTS_OK: top-level-404=present; spa-fallback=disabled-for-unknown-paths; scripts=0; external-assets=0; api-material=0; static-csp=covered')
