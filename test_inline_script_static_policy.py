from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'inline_script_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')
VERCEL = (ROOT / 'vercel.json').read_text(encoding='utf-8')

required_finalizer = (
    'EXPECTED_INLINE_COUNT = 3',
    "if len(matches) != EXPECTED_INLINE_COUNT",
    "if disallowed:",
    "script_type not in ('', 'text/javascript', 'application/javascript', 'module')",
    "if 'document.currentScript' in body:",
    "if remaining_inline:",
    "app-inline-{idx:02d}.js",
    "execution-order=preserved",
)
missing = [marker for marker in required_finalizer if marker not in FINALIZER]
if missing:
    raise SystemExit('INLINE_SCRIPT_STATIC_POLICY_FAILED: finalizer guard missing: ' + ', '.join(missing))

calls = (
    'python3 test_script_attr_csp_readiness.py',
    'python3 test_inline_script_static_policy.py',
    'python3 inline_script_static_finalize.py',
    'python3 test_inline_script_static_output.py',
    'python3 test_vue_runtime_csp_readiness.py',
)
for call in calls:
    if BUILD.count(call) != 1:
        raise SystemExit('INLINE_SCRIPT_STATIC_POLICY_FAILED: build call must appear once: ' + call)
positions = [BUILD.index(call) for call in calls]
if positions != sorted(positions):
    raise SystemExit('INLINE_SCRIPT_STATIC_POLICY_FAILED: readiness/policy/finalize/output/Vue gate order drifted')

csp_line = next((line for line in VERCEL.splitlines() if 'Content-Security-Policy' in line), '')
script_part = csp_line.split('script-src ', 1)[1].split(';', 1)[0] if 'script-src ' in csp_line else ''
tokens = script_part.split()
if tokens != ["'self'", "'unsafe-eval'"]:
    raise SystemExit('INLINE_SCRIPT_STATIC_POLICY_FAILED: script-src must be same-origin plus Vue compiler eval only')
if "'unsafe-inline'" in script_part:
    raise SystemExit('INLINE_SCRIPT_STATIC_POLICY_FAILED: script-src unsafe-inline returned')

print('INLINE_SCRIPT_STATIC_POLICY_OK: expected=3; attrs=executable-only; currentScript=denied; order=readiness>policy>finalize>output>vue; script=self+vue-eval; unsafe-inline=absent')
