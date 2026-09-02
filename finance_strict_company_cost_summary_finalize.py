from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
REGISTRY = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'
OLD_COPY = '已包含公司成本 + 公司项目成本；详细构成在下方成本模块查看。'
NEW_COPY = '仅统计公司公共成本 + 公司项目成本；详细构成在下方成本模块查看。'


def fail(message):
    raise SystemExit('FINANCE_STRICT_COMPANY_COST_SUMMARY_FINALIZE_FAILED: ' + message)


def method_bounds(text, name):
    signature = re.compile(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', re.M)
    match = signature.search(text)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    tail = text[start:]
    defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
    if len(defs) < 2 or defs[0].group(1) != name:
        fail(name + ' boundary parser drifted')
    end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
    return start, end


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no app-inline artifacts')

# The top-level total-cost card is strictly company-owned cost. A cost carrying a
# clientId is customer-owned even if an older/imported record still has a stale
# COMPANY scope value, so client ownership takes precedence over the legacy scope.
strict_method = (
    "financeCompanySummaryCostGroups(){const g={};"
    "this.financeCosts.filter(c=>{const scope=c.clientId?'CLIENT':(c.scope||'COMPANY');"
    "return this.financeDateMatch(c.date)&&['COMPANY','COMPANY_PROJECT'].includes(scope)})"
    ".forEach(c=>{const cur=c.currency||'USD';g[cur]=(g[cur]||0)+Number(c.amount||0)});return g},\n"
)
old_return = "return this.spendGroupsText(this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
new_return = "const groups=this.financeCompanySummaryCostGroups;return this.spendGroupsText(typeof groups==='function'?groups.call(this):groups)"

# The live finance template renders financeCostGroups directly in both the upper
# KPI card and the lower cost-summary card. Therefore fixing financeCostText alone
# is insufficient. Make the ALL-client financeCostGroups getter delegate to the
# strict company-only authority before any locked-period snapshot can return the
# historical all-cost aggregate. Selected-client behavior remains unchanged.
# The typeof fallback keeps direct method-extraction regression tests compatible;
# in Vue runtime `this.financeCompanySummaryCostGroups` is the unwrapped computed value.
cost_groups_anchor = "financeCostGroups(){const snap=this.financeActiveSnapshotScope;"
cost_groups_replacement = (
    "financeCostGroups(){if(this.financeClientFilter==='ALL'){const groups=this.financeCompanySummaryCostGroups;"
    "return typeof groups==='function'?groups.call(this):groups}const snap=this.financeActiveSnapshotScope;"
)

hits = 0
cost_group_hits = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')

    cost_bounds = method_bounds(text, 'financeCostGroups')
    if cost_bounds is not None:
        cost_group_hits += 1
        start, end = cost_bounds
        source = text[start:end].rstrip()
        if source.count(cost_groups_anchor) != 1:
            fail('financeCostGroups all-client anchor drifted')
        patched_source = source.replace(cost_groups_anchor, cost_groups_replacement, 1)
        text = text[:start] + patched_source + text[end:]

    bounds = method_bounds(text, 'financeCostText')
    if bounds is None:
        continue
    hits += 1
    if 'financeCompanySummaryCostGroups(){' in text:
        fail('strict authority already present before finalize')
    start, end = bounds
    source = text[start:end].rstrip()
    if source.count(old_return) != 1:
        fail('financeCostText broad-company anchor drifted')
    patched = source.replace(old_return, new_return, 1)
    output = text[:start] + strict_method + patched + text[end:]
    path.write_text(output, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(output.encode('utf-8')).hexdigest()))

if hits != 1:
    fail(f'financeCostText expected once, found {hits}')
if cost_group_hits != 1:
    fail(f'financeCostGroups expected once, found {cost_group_hits}')

if not REGISTRY.is_file():
    fail('render registry missing')
registry = REGISTRY.read_text(encoding='utf-8')
if registry.count(OLD_COPY) != 1:
    fail(f'prior company-summary copy expected once, found {registry.count(OLD_COPY)}')
if NEW_COPY in registry:
    fail('strict summary copy already present')
registry = registry.replace(OLD_COPY, NEW_COPY, 1)
REGISTRY.write_text(registry, encoding='utf-8')
registry_sha = hashlib.sha256(registry.encode('utf-8')).hexdigest()

print(
    'FINANCE_STRICT_COMPANY_COST_SUMMARY_FINALIZE_OK: '
    'scope=COMPANY+COMPANY_PROJECT; client-owned+allocated-shared=excluded; '
    'clientId-precedence=true; all-template-bindings=financeCostGroups-strict; '
    'selected-client-cost=preserved; legacy-locked-periods=raw-cost-recompute; '
    f'registry={registry_sha[:12]}; app=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
