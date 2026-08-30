from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'frontend_vendor_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required = (
    'https://unpkg.com/vue@3.5.41/dist/vue.global.js',
    '14625269265de97b5c344b8fcfb7136c0c9ab09f7dbadc909a4967d14eca05fb',
    'vue-3.5.41.global.js',
    'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
    'c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99',
    'xlsx-0.18.5.full.min.js',
    "parsed.scheme != 'https'",
    'unexpected redirect',
    'SHA-256 mismatch',
    'browser-external-js=removed',
    'DOWNLOAD_ATTEMPTS = 3',
    'for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):',
    'time.sleep(attempt)',
    'download failed after {DOWNLOAD_ATTEMPTS} attempts',
    'download-attempts<={DOWNLOAD_ATTEMPTS}',
)
missing = [marker for marker in required if marker not in FINALIZER]
if missing:
    raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED missing: ' + ', '.join(missing))

for forbidden in ('__PROBE__', '/vue@3/', '/xlsx@latest', 'http://'):
    if forbidden in FINALIZER:
        raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED forbidden marker: ' + forbidden)

# Retry scope must remain transport-only. Redirect denial happens inside the
# request attempt and raises immediately, while byte-shape/marker/SHA validation
# happens only after the retry loop has produced one successful response.
retry_start = FINALIZER.index('for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):')
redirect_check = FINALIZER.index('unexpected redirect', retry_start)
retry_break = FINALIZER.index('last_error = None\n        break', retry_start)
sha_check = FINALIZER.index("if actual != vendor['sha256']:", retry_break)
if not (retry_start < redirect_check < retry_break < sha_check):
    raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED retry/security validation order drift')
if FINALIZER.count('time.sleep(attempt)') != 1:
    raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED retry backoff count drift')

policy_call = 'python3 test_frontend_vendor_static_policy.py'
finalizer_call = 'python3 frontend_vendor_static_finalize.py'
output_call = 'python3 test_frontend_dependency_pin_output.py'
for call in (policy_call, finalizer_call, output_call):
    if BUILD.count(call) != 1:
        raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED build call count: ' + call)
if not (BUILD.index('python3 tailwind_static_finalize.py') < BUILD.index(policy_call) < BUILD.index(finalizer_call) < BUILD.index(output_call)):
    raise SystemExit('FRONTEND_VENDOR_STATIC_POLICY_FAILED build order drift')

print('FRONTEND_VENDOR_STATIC_POLICY_OK: vue=3.5.41+sha256; xlsx=0.18.5+sha256; redirects=denied; transport-retries<=3; validation=fail-closed-after-fetch; output=same-origin; build-order=guarded')
