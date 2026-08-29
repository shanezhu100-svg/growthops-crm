from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'inline_style_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required_finalizer_markers = (
    'EXPECTED_STYLE_COUNT = 4',
    "'growthops-session-restore-style'",
    "'growthops-credential-v6-placeholder-style'",
    "'growthops-module-home-navigation-style'",
    "if '@import' in low_css",
    'validate_base_stable_urls(css, idx)',
    "lower.startswith('data:')",
    "value.startswith('/') and not value.startswith('//')",
    "lower.startswith('https://')",
    'base-relative or unsupported CSS url',
    "name = f'app-style-{idx:02d}.css'",
    "href = f'/app/{name}'",
    'first-party-js-id-refs=0',
    'style-blocks=0',
)
missing = [marker for marker in required_finalizer_markers if marker not in FINALIZER]
if missing:
    raise SystemExit('INLINE_STYLE_STATIC_POLICY_FAILED: finalizer policy marker missing: ' + ', '.join(missing))

calls = (
    'python3 test_style_csp_readiness.py',
    'python3 test_inline_style_static_policy.py',
    'python3 inline_style_static_finalize.py',
    'python3 test_inline_style_static_output.py',
)
for call in calls:
    if BUILD.count(call) != 1:
        raise SystemExit('INLINE_STYLE_STATIC_POLICY_FAILED: build call must occur exactly once: ' + call)
positions = [BUILD.index(call) for call in calls]
if positions != sorted(positions):
    raise SystemExit('INLINE_STYLE_STATIC_POLICY_FAILED: style migration build order drifted')

print(
    'INLINE_STYLE_STATIC_POLICY_OK: styles=4; reviewed-ids=3; @import=denied; '
    'urls=data+root-relative+https-only; relative+protocol-relative=denied; '
    'order=readiness>policy>finalize>output'
)
