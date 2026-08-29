from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'style_attr_cssom_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required = (
    'ROAS_OLD =',
    'ROAS_NEW =',
    '<progress class="growthops-roas-progress"',
    ':value="bar.width"',
    "PENDING_OLD = \"row.style.visibility='visible'; row.style.pointerEvents='none';",
    "READY_OLD = \"row.style.visibility='visible'; row.style.pointerEvents='';",
    "COPY_OLD = \"ta.style.position='fixed';ta.style.opacity='0';\"",
    "COPY_NEW = \"ta.className='growthops-clipboard-fallback';\"",
    '[data-growthops-credential-v6-gate="pending"]',
    '.growthops-roas-progress.bg-blue-600::-webkit-progress-value',
    '.growthops-roas-progress.bg-slate-950::-webkit-progress-value',
    'if html.count(ROAS_OLD) != 1',
    'if js2.count(PENDING_OLD) != 2',
    'if js2.count(READY_OLD) != 1',
    'if js3.count(COPY_OLD) != 1',
)
missing = [marker for marker in required if marker not in FINALIZER]
if missing:
    raise SystemExit('STYLE_ATTR_CSSOM_POLICY_FAILED: finalizer marker missing: ' + ', '.join(missing))

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

print('STYLE_ATTR_CSSOM_POLICY_OK: roas=native-progress; credential=data-state-css; clipboard=class-css; anchors=fail-closed; order=guarded')
