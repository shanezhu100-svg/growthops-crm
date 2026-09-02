from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_COST_MONTH_LOCK_GUARD_FINALIZE_FAILED: ' + message)


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

# syncOpeningFeeCost historically guarded only the destination month before
# Object.assign(existing,payload). That allowed a cost already recorded in a locked
# month to be relocated/re-priced by editing its source opening deal into an open
# month. The existing/origin month is historical finance truth and must fail closed
# before any eligibility, destination, or payload mutation is evaluated.
old = (
    "const existing=this.financeCosts.find(c=>c.sourceType==='OPENING_DEAL'&&String(c.sourceId)===String(deal.id));"
    "const should=deal.status==='OPENED'&&deal.clientId&&Number(deal.fee||0)>0;"
)
new = (
    "const existing=this.financeCosts.find(c=>c.sourceType==='OPENING_DEAL'&&String(c.sourceId)===String(deal.id));"
    "const existingMonth=String(existing?.date||'').slice(0,7);"
    "if(existing&&existingMonth&&this.isMonthLocked(existingMonth)){"
    "if(!silent)this.notify(`开户费原成本所在 ${existingMonth} 已月结，未自动改动历史成本`);return 0}"
    "const should=deal.status==='OPENED'&&deal.clientId&&Number(deal.fee||0)>0;"
)

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'syncOpeningFeeCost')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if 'existingMonth=' in source or '开户费原成本所在' in source:
        fail('syncOpeningFeeCost already contains origin-month guard')
    if source.count(old) != 1:
        fail(f'syncOpeningFeeCost origin-lock anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'syncOpeningFeeCost expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'OPENING_COST_MONTH_LOCK_GUARD_FINALIZE_OK: '
    'origin-month=locked-immutable; destination-lock=preserved; '
    'unlocked-to-unlocked=preserved; disqualification=origin-lock-aware; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
