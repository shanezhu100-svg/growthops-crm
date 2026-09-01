from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
REGISTRY = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'

OLD_COPY = '已包含客户专属成本 + 公司项目成本 + 公司公共成本；详细构成在下方成本模块查看。'
NEW_COPY = '已包含公司成本 + 公司项目成本；详细构成在下方成本模块查看。'


def fail(message: str) -> None:
    raise SystemExit('FINANCE_COMPANY_COST_SUMMARY_FINALIZE_FAILED: ' + message)


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
    fail('dist/app missing; run final runtime build first')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts found')

# The company/all-clients summary must use the same reviewed cost authority already
# used by company profit: company public/shared costs + company-project costs, with
# direct CLIENT/customer-owned costs excluded. A selected client keeps the existing
# scoped financeCostGroups behavior so client detail/profit semantics do not change.
method_name = 'financeCostText'
method_hits = 0
changed_app = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, method_name)
    if bounds is None:
        continue
    method_hits += 1
    start, end = bounds
    source = text[start:end].rstrip()
    old = 'return this.spendGroupsText(this.financeCostGroups)'
    new = "return this.spendGroupsText(this.financeClientFilter==='ALL'?this.financeCompanyNonClientCostGroups:this.financeCostGroups)"
    if source.count(old) != 1:
        fail(f'{method_name} expected one full-cost anchor, found {source.count(old)}')
    if 'financeCompanyNonClientCostGroups' in source:
        fail(f'{method_name} already contains company-only summary authority')
    patched = source.replace(old, new, 1)
    output = text[:start] + patched + text[end:]
    path.write_text(output, encoding='utf-8')
    changed_app.append((path.name, hashlib.sha256(output.encode('utf-8')).hexdigest()))

if method_hits != 1:
    fail(f'{method_name} expected in exactly one app-inline artifact, found {method_hits}')

# Vue templates are already compiled by this stage. Update only the reviewed text
# literal in the deterministic render registry; no render structure or executable
# expression changes. The old copy is forbidden because it incorrectly says the
# company total includes customer-specific costs.
if not REGISTRY.is_file():
    fail('render registry missing')
registry = REGISTRY.read_text(encoding='utf-8')
if registry.count(OLD_COPY) != 1:
    fail(f'old summary copy expected exactly once, found {registry.count(OLD_COPY)}')
if NEW_COPY in registry:
    fail('new summary copy already present before correction')
registry = registry.replace(OLD_COPY, NEW_COPY, 1)
if OLD_COPY in registry or registry.count(NEW_COPY) != 1:
    fail('summary copy replacement drifted')
REGISTRY.write_text(registry, encoding='utf-8')
registry_sha = hashlib.sha256(registry.encode('utf-8')).hexdigest()

print(
    'FINANCE_COMPANY_COST_SUMMARY_FINALIZE_OK: '
    'all-summary=company+company-project-only; direct-client-cost=excluded; '
    'selected-client-cost=preserved; client-cost-copy=absent; '
    f'registry={registry_sha[:12]}; app=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed_app)
)
