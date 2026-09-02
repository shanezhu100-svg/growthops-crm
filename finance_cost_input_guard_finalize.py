from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('FINANCE_COST_INPUT_GUARD_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    signature = re.compile(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', re.M)
    match = signature.search(text)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    tail = text[start:]
    defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
    if len(defs) < 2 or defs[0].group(1) != name:
        fail(f'{name} boundary parser drifted')
    end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
    return start, end


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = {'saveFinanceCost': 0, 'ensureAutomaticAssetCosts': 0, 'createReceivableForClientMonth': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text

    bounds = method_bounds(text, 'saveFinanceCost')
    if bounds is not None:
        found['saveFinanceCost'] += 1
        start, end = bounds
        source = text[start:end]
        marker = 'financeCostAmountCheck='
        if marker in source:
            fail('saveFinanceCost already contains finance cost amount guard')
        signature = re.match(r'saveFinanceCost\(\)\s*\{', source)
        if not signature:
            fail('saveFinanceCost signature drifted')
        guard = (
            "const financeCostAmountCheck=Number(this.costForm&&this.costForm.amount!=null&&this.costForm.amount!==''?this.costForm.amount:0);"
            "if(!Number.isFinite(financeCostAmountCheck)||financeCostAmountCheck<0){this.notify('请输入有效成本');return}"
        )
        source = source[:signature.end()] + guard + source[signature.end():]
        text = text[:start] + source + text[end:]

    bounds = method_bounds(text, 'ensureAutomaticAssetCosts')
    if bounds is not None:
        found['ensureAutomaticAssetCosts'] += 1
        start, end = bounds
        source = text[start:end]
        old = "if(env.autoCost===false||Number(env.ipMonthlyFee||0)<=0)return;"
        new = (
            "const ipMonthlyFeeCheck=Number(env.ipMonthlyFee||0);"
            "if(env.autoCost===false||!Number.isFinite(ipMonthlyFeeCheck)||ipMonthlyFeeCheck<=0)return;"
        )
        if source.count(old) != 1:
            fail(f'ensureAutomaticAssetCosts monthly-fee anchor expected once, found {source.count(old)}')
        if 'ipMonthlyFeeCheck=' in source:
            fail('ensureAutomaticAssetCosts already contains finite monthly-fee guard')
        source = source.replace(old, new, 1)
        text = text[:start] + source + text[end:]

    bounds = method_bounds(text, 'createReceivableForClientMonth')
    if bounds is not None:
        found['createReceivableForClientMonth'] += 1
        start, end = bounds
        source = text[start:end]
        monthly_old = "if(!client||client.archived||!month||(client.billingMode||'FULL_MONTH')==='MANUAL'||Number(client.monthlyFee||0)<=0||this.isMonthLocked(month))return 0;"
        monthly_new = (
            "const receivableMonthlyFeeCheck=Number(client&&client.monthlyFee||0);"
            "if(!client||client.archived||!month||(client.billingMode||'FULL_MONTH')==='MANUAL'||!Number.isFinite(receivableMonthlyFeeCheck)||receivableMonthlyFeeCheck<=0||this.isMonthLocked(month))return 0;"
        )
        amount_old = "const amount=this.financeServiceFeeForClientMonth(client,month);if(amount<=0)return 0;"
        amount_new = "const amount=this.financeServiceFeeForClientMonth(client,month);if(!Number.isFinite(amount)||amount<=0)return 0;"
        if source.count(monthly_old) != 1:
            fail(f'createReceivableForClientMonth monthly-fee anchor expected once, found {source.count(monthly_old)}')
        if source.count(amount_old) != 1:
            fail(f'createReceivableForClientMonth calculated-amount anchor expected once, found {source.count(amount_old)}')
        if 'receivableMonthlyFeeCheck=' in source or '!Number.isFinite(amount)||amount<=0' in source:
            fail('createReceivableForClientMonth finite guards already present')
        source = source.replace(monthly_old, monthly_new, 1).replace(amount_old, amount_new, 1)
        text = text[:start] + source + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if not changed:
    fail('no final runtime artifact changed')

print(
    'FINANCE_COST_INPUT_GUARD_FINALIZE_OK: '
    'manual-cost=finite-nonnegative; automatic-ip-monthly-fee=finite-positive; '
    'automatic-receivable-monthly-fee+calculated-amount=finite-positive; '
    'nan+infinity=denied-before-cost-or-receivable-mutation; existing-lock+audit+persistence=preserved; '
    + 'artifacts=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
