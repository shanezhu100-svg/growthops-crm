from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'inter_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required = (
    "CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'",
    "CSS_SHA256 = 'ccb4927c1e665717c1f91e480fbbad168db8c70373b7ccf7abf2f70131c04de3'",
    'CSS_SIZE = 12355',
    "'latin': ('3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62', 48256, 'inter-latin.woff2')",
    "'latin-ext': ('34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956', 85068, 'inter-latin-ext.woff2')",
    "EXPECTED_WEIGHTS = (400, 500, 600, 700, 800)",
    "EXPECTED_SUBSETS = ('latin-ext', 'latin')",
    "LOCAL_CSS_TAG = '<link rel=\"stylesheet\" href=\"/vendor/inter/inter.css\" />'",
    "if final_url != url:",
    "fail('unexpected redirect: ' + final_url)",
    "if len(urls) != 1:",
    "Inter latin and latin-ext unexpectedly resolve to the same upstream URL",
    "Only after every network input has passed its exact digest/size inventory",
    "browser-google-fonts=removed",
)
missing = [marker for marker in required if marker not in FINALIZER]
if missing:
    raise SystemExit('INTER_STATIC_POLICY_FAILED missing finalizer guard: ' + ', '.join(missing))

for forbidden in ('__PROBE__', 'latest', 'fonts.googleapis.com/css?family='):
    if forbidden in FINALIZER:
        raise SystemExit('INTER_STATIC_POLICY_FAILED forbidden floating/probe marker: ' + forbidden)

policy_call = 'python3 test_inter_static_policy.py'
finalizer_call = 'python3 inter_static_finalize.py'
output_call = 'python3 test_frontend_dependency_pin_output.py'
for call in (policy_call, finalizer_call, output_call):
    if BUILD.count(call) != 1:
        raise SystemExit('INTER_STATIC_POLICY_FAILED build call count drift: ' + call)
if not (BUILD.index(policy_call) < BUILD.index(finalizer_call) < BUILD.index(output_call)):
    raise SystemExit('INTER_STATIC_POLICY_FAILED build order must be policy > finalizer > output gate')
if BUILD.index(finalizer_call) < BUILD.index('python3 fontawesome_static_finalize.py'):
    raise SystemExit('INTER_STATIC_POLICY_FAILED Inter finalizer must run after other browser dependency finalizers')

print('INTER_STATIC_POLICY_OK: css+2-variable-fonts=sha256+size-pinned; weights=5; subsets=latin+latin-ext; redirects=denied; deduplicated-before-write; output=same-origin')
