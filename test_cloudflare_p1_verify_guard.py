from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERIFY = (ROOT / 'cloudflare_p1_verify.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

# Keep the production artifact parity pins synchronized while extending the
# final Cloudflare verifier with the fail-open 404 and static-header boundary.
EXPECTED_PINS = {
    'index.html': '19637585e93ea63a9c6d03ce6e4c6f6454b35e2018610a02cbbcd58cfa797b42',
    'cloud-adapter.js': '9713943a80008f625000d6fac2440fb9395f9e6e2c1fd09e820a399c5c34379f',
    'cloud-security-hotfix.js': 'f2b3f08c9bbabc4e974c859fe6d86396d028f46b43354b6d74572b5efa938194',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': 'b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7',
}
for name, digest in EXPECTED_PINS.items():
    marker = repr(name) + ': ' + repr(digest)
    if marker not in VERIFY:
        raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED production pin drift: ' + name)

required_verify_markers = (
    "DIST / '404.html'",
    "DIST / '_headers'",
    "headers.startswith('/*\\n')",
    'Content-Security-Policy:',
    'X-Frame-Options:',
    'X-Content-Type-Options:',
    'Referrer-Policy:',
    'Permissions-Policy:',
    'Cross-Origin-Opener-Policy:',
    'noindex,nofollow,noarchive',
    "'<script'",
    "'<form'",
    "'<iframe'",
    "'fetch('",
    "'xmlhttprequest'",
    '/api/crm',
    'sb_secret_',
    'growthops_supabase',
    'document.cookie',
    'localstorage',
    'sessionstorage',
    "re.search(r'\\b(?:src|href|action)\\s*='",
    'failopen_404=guarded',
    'static_headers=guarded',
)
missing = [marker for marker in required_verify_markers if marker not in VERIFY]
if missing:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED verifier coverage missing: ' + ', '.join(missing))

# build.sh keeps a static verifier-source guard in the canonical build itself.
# CI additionally executes the final pinned-output verifier after build.sh so
# Cloudflare-specific output drift is rejected before a PR can be merged.
call = 'python3 test_cloudflare_p1_verify_guard.py'
if BUILD.count(call) != 1:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED static verifier gate not wired exactly once')
if BUILD.index(call) < BUILD.index('python3 test_cloudflare_failopen_404.py'):
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED verifier gate runs before 404 build test')

print('CLOUDFLARE_P1_VERIFY_GUARD_TESTS_OK: production-pins=5-synchronized; final-404-check=required; wildcard-static-headers=6-required; active-material-deny=required')
