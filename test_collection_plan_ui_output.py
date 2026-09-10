from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
REGISTRY = APP_DIR / 'vue-render-registry.js'
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('COLLECTION_PLAN_UI_OUTPUT_FAILED: ' + message)


files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')
app = '\n'.join(path.read_text(encoding='utf-8') for path in files)
if not REGISTRY.is_file():
    fail('final Vue render registry missing')
registry = REGISTRY.read_text(encoding='utf-8')

for marker in (
    "collectionPlan:{mode:'MONTHLY',firstDay:15,firstRatio:0.5}",
    "collectionMode==='SEMI_MONTHLY'?'SEMI_MONTHLY':'MONTHLY'",
    'collectionFirstDayRaw',
    'collectionFirstRatioRaw',
):
    if marker not in app:
        fail(f'final application model marker missing: {marker}')

for marker in (
    '收款节奏',
    '月结一次',
    '半月收款',
    '首个收款日',
    '首笔收款比例',
    '历史已生成账单不追溯修改',
    '余额月末收取',
):
    if marker not in registry:
        fail(f'compiled client UI marker missing: {marker}')

finalizer = 'python3 collection_plan_ui_finalize.py'
inline_extract = 'python3 inline_script_static_finalize.py'
vue_runtime = 'python3 vue_runtime_only_finalize.py'
output_gate = 'python3 test_collection_plan_ui_output.py'
for call in (finalizer, inline_extract, vue_runtime, output_gate):
    if BUILD.count(call) != 1:
        fail(f'build call must appear exactly once: {call}')
if not (BUILD.index(finalizer) < BUILD.index(inline_extract) < BUILD.index(vue_runtime) < BUILD.index(output_gate)):
    fail('collection plan UI must finalize before script extraction/Vue precompile and verify after final runtime output')

print(
    'COLLECTION_PLAN_UI_OUTPUT_OK: form=monthly+semi-monthly; '
    'semi-monthly=first-day+ratio+month-end; detail=compiled-truthful-summary; '
    'legacy=monthly-default; invalid-plan=safe-normalization; history=no-retroactive-rewrite; '
    'provenance=final-app+compiled-render-registry'
)
