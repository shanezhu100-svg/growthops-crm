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


def patch_profit(source: str, name: str) -> str:
    old = 'return this.subtractSpendGroups(income,this.financeCostGroups)'
    new = "return this.subtractSpendGroups(income,this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
    if source.count(old) != 1:
        fail(f'{name} expected one total-cost anchor, found {source.count(old)}')
    if 'financeCompanyNonClientCostGroups' in source:
        fail(f'{name} already contains non-client cost authority')
    return source.replace(old, new, 1)


def patch_actual(source: str) -> str:
    return patch_profit(source, 'financeActualNetProfitGroups')


def patch_expected(source: str) -> str:
    return patch_profit(source, 'financeExpectedNetProfitGroups')


def patch_breakdown(source: str) -> str:
    # Every cost reference participates in the same breakdown (currency inventory,
    # displayed cost, and formatted cost). At ALL/company scope BOTH EXPECTED and
    # ACTUAL use company/non-client costs. A selected client keeps its existing
    # financeCostGroups basis so client profitability semantics do not change.
    old = 'this.financeCostGroups'
    new = "(this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
    count = source.count(old)
    if count != 3:
        fail(f'financeProfitBreakdownRows expected three cost-group references, found {count}')
    if 'financeCompanyNonClientCostGroups' in source:
        fail('financeProfitBreakdownRows already contains non-client cost authority')
    return source.replace(old, new)


def replace_last(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 2:
        fail(f'buildFinanceMonthSnapshot expected two {label} anchors, found {source.count(old)}')
    pos = source.rfind(old)
    if pos < 0:
        fail(f'buildFinanceMonthSnapshot company {label} anchor missing')
    return source[:pos] + new + source[pos + len(old):]


def patch_snapshot(source: str) -> str:
    # The method contains one client-row calculation and one company/all-clients
    # calculation for both expected and actual profit. Preserve client calculations;
    # company snapshots exclude direct CLIENT costs from BOTH expected and actual
    # net profit so future locked months use the same reviewed company cost basis.
    expected_old = 'expectedNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,expectedRebateGroups),costGroups)'
    expected_new = 'expectedNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,expectedRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))'
    actual_old = 'actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),costGroups)'
    actual_new = 'actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))'
    source = replace_last(source, expected_old, expected_new, 'expected-profit')
    source = replace_last(source, actual_old, actual_new, 'actual-profit')
    return source


patchers = {
    'financeActualNetProfitGroups': patch_actual,
    'financeExpectedNetProfitGroups': patch_expected,
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
    'scope=ALL-expected+confirmed; client-direct-cost=excluded-from-company-profit; '
    'selected-client-cost=preserved; breakdown=company-cost-only-at-ALL; '
    'future-snapshot=expected+actual-aligned; '
    + 'artifacts=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed_files)
)

# Keep narrowly scoped business integrity guards in the same pre-render correction
# stage so final browser/business regression tests execute the guarded shipped code.
import archived_client_receivable_guard_finalize  # noqa: E402,F401
import receivable_reminder_close_finalize  # noqa: E402,F401
import receivable_payment_amount_guard_finalize  # noqa: E402,F401
import receivable_payment_date_guard_finalize  # noqa: E402,F401
import lead_client_stale_edit_guard_finalize  # noqa: E402,F401
import lead_client_financial_input_guard_finalize  # noqa: E402,F401
import ad_data_input_guard_finalize  # noqa: E402,F401
