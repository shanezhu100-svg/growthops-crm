from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'style_attr_cssom_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required = (
    'ROAS_OLD =',
    'ROAS_NEW =',
    '<progress class="growthops-roas-progress"',
    ':value="bar.width"',
    "ROW_VISIBILITY = \"row.style.visibility='visible';\"",
    "ROW_PENDING_POINTER = \"row.style.pointerEvents='none';\"",
    "ROW_READY_POINTER = \"row.style.pointerEvents='';\"",
    "COPY_POSITION = \"ta.style.position='fixed';\"",
    "COPY_OPACITY = \"ta.style.opacity='0';\"",
    "COPY_CLASS = \"ta.className='growthops-clipboard-fallback';\"",
    '[data-growthops-credential-v6-gate="pending"]',
    '.growthops-roas-progress.bg-blue-600::-webkit-progress-value',
    '.growthops-roas-progress.bg-slate-950::-webkit-progress-value',
    'if html.count(ROAS_OLD) != 1',
    "(ROW_VISIBILITY, 3, 'credential visibility')",
    "(ROW_PENDING_POINTER, 2, 'credential pending pointerEvents')",
    "(ROW_READY_POINTER, 1, 'credential ready pointerEvents')",
    'if js3.count(COPY_POSITION) != 1',
    'if js3.count(COPY_OPACITY) != 1',
    "js2 = js2.replace(ROW_VISIBILITY, '')",
    "js2 = js2.replace(ROW_PENDING_POINTER, '')",
    "js2 = js2.replace(ROW_READY_POINTER, '')",
    'js3 = js3.replace(COPY_POSITION, COPY_CLASS, 1)',
    "js3 = js3.replace(COPY_OPACITY, '', 1)",
)
missing = [marker for marker in required if marker not in FINALIZER]
if missing:
    raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: finalizer marker missing: ' + ', '.join(missing))

# Do not allow the old compound-string anchors back in; they made the migration
# sensitive to formatting rather than the reviewed semantic sink inventory.
for forbidden in ('PENDING_OLD =', 'READY_OLD =', 'COPY_OLD ='):
    if forbidden in FINALIZER:
        raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: brittle compound anchor returned: ' + forbidden)

calls = (
    'python3 test_style_csp_readiness.py',
    'python3 inline_style_static_finalize.py',
    'python3 test_inline_style_static_output.py',
    'python3 test_style_attr_cssom_policy.py',
    'python3 style_attr_cssom_finalize.py',
    'python3 test_style_attr_cssom_output.py',
)
for call in calls:
    if BUILD.count(call) != 1:
        raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: build call must occur exactly once: ' + call)
pos = [BUILD.index(call) for call in calls]
if pos != sorted(pos):
    raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: build order drifted')
if 'test_style_attr_cssom_probe.py' in BUILD:
    raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: fail-closed probe remains in canonical build')

print(
    'STYLE_ATTR_CSSOM_POLICY_OK: roas=native-progress; credential=data-state-css; '
    'clipboard=class-css; anchors=atomic-counted-fail-closed; order=guarded'
)
