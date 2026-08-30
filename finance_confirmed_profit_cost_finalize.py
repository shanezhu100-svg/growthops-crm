from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('FINANCE_CONFIRMED_PROFIT_COST_FINALIZE_FAILED: ' + message)


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
    # Keep the separator comma/newline owned by the next method outside the replacement.
    return start, end


def replace_method(text: str, name: str, patcher):
    bounds = method_bounds(text, name)
    if bounds is None:
        return text, False
    start, end = bounds
    original = text[start:end].rstrip()
    patched = patcher(original)
    if patched == original:
        fail(f'{name} patch made no change')
    return text[:start] + patched + text[end:], True


if not APP_DIR.is_dir():
    fail('dist/app missing; run final runtime build first')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts found')


def patch_actual(source: str) -> str:
    old = 'return this.subtractSpendGroups(income,this.financeCostGroups)'
    new = "return this.subtractSpendGroups(income,this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
    if source.count(old) != 1:
        fail(f'financeActualNetProfitGroups expected one total-cost anchor, found {source.count(old)}')
    if 'financeCompanyNonClientCostGroups' in source:
        fail('financeActualNetProfitGroups already contains non-client cost authority')
    return source.replace(old, new, 1)


def patch_breakdown(source: str) -> str:
    old = 'this.financeCostGroups'
    new = "(mode==='ACTUAL'&&this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
    count = source.count(old)
    if count != 1:
        fail(f'financeProfitBreakdownRows expected one cost-group reference, found {count}')
    if 'financeCompanyNonClientCostGroups' in source:
        fail('financeProfitBreakdownRows already contains non-client cost authority')
    return source.replace(old, new, 1)


def patch_snapshot(source: str) -> str:
    # The method contains one client-row calculation and one company/all-clients
    # calculation. Preserve the client calculation; only the final company snapshot
    # excludes direct CLIENT costs that have already been attributed to clients.
    old = 'actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),costGroups)'
    if source.count(old) != 2:
        fail(f'buildFinanceMonthSnapshot expected two actual-profit anchors, found {source.count(old)}')
    new = 'actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))'
    pos = source.rfind(old)
    if pos < 0:
        fail('buildFinanceMonthSnapshot company actual-profit anchor missing')
    return source[:pos] + new + source[pos + len(old):]


patchers = {
    'financeActualNetProfitGroups': patch_actual,
    'financeProfitBreakdownRows': patch_breakdown,
    'buildFinanceMonthSnapshot': patch_snapshot,
}
found = {name: 0 for name in patchers}
changed_files = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, patcher in patchers.items():
        text, changed = replace_method(text, name, patcher)
        if changed:
            found[name] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed_files.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if not changed_files:
    fail('no final runtime artifact changed')

print(
    'FINANCE_CONFIRMED_PROFIT_COST_FINALIZE_OK: '
    'scope=ALL-confirmed-only; client-direct-cost=excluded-from-aggregate; '
    'selected-client-cost=preserved; expected-profit=unchanged; future-snapshot=aligned; '
    + 'artifacts=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed_files)
)
