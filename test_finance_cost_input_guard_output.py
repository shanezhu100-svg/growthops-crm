from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('FINANCE_COST_INPUT_GUARD_OUTPUT_FAILED: ' + message)


def extract(name: str) -> str:
    files = sorted(APP_DIR.glob('app-inline-*.js'))
    hits = []
    for path in files:
        text = path.read_text(encoding='utf-8')
        match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, re.M)
        if not match:
            continue
        start = match.start() + match.group(0).index(match.group(1))
        tail = text[start:]
        defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
        if len(defs) < 2 or defs[0].group(1) != name:
            fail(f'{name} boundary parser drifted')
        end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
        hits.append(text[start:end])
    if len(hits) != 1:
        fail(f'{name} expected exactly once, found {len(hits)}')
    return hits[0]


save = extract('saveFinanceCost')
auto = extract('ensureAutomaticAssetCosts')
for marker in (
    'financeCostAmountCheck=',
    '!Number.isFinite(financeCostAmountCheck)',
    'financeCostAmountCheck<0',
):
    if save.count(marker) != 1:
        fail(f'saveFinanceCost marker drift: {marker}')
for marker in (
    'ipMonthlyFeeCheck=',
    '!Number.isFinite(ipMonthlyFeeCheck)',
    'ipMonthlyFeeCheck<=0',
):
    if auto.count(marker) != 1:
        fail(f'ensureAutomaticAssetCosts marker drift: {marker}')
if 'if(env.autoCost===false||Number(env.ipMonthlyFee||0)<=0)return;' in auto:
    fail('legacy non-finite-permissive IP monthly fee guard remains')

finalizer = 'python3 finance_cost_input_guard_finalize.py'
output_gate = 'python3 test_finance_cost_input_guard_output.py'
business_root = 'node test_business_receivable_reminder_probe.mjs'
for call in (finalizer, output_gate):
    if BUILD.count(call) != 1:
        fail(f'build call must appear exactly once: {call}')
if not (BUILD.index(finalizer) < BUILD.index(output_gate) < BUILD.index(business_root)):
    fail('finance cost input guard must finalize+verify before business regressions')

print('FINANCE_COST_INPUT_GUARD_OUTPUT_OK: manual-cost=finite-nonnegative; auto-ip-fee=finite-positive; legacy-nonfinite-path=absent; build-order=guarded')
