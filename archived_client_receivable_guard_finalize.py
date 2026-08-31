from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('ARCHIVED_CLIENT_RECEIVABLE_GUARD_FINALIZE_FAILED: ' + message)


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

anchor = "if(!this.assertMonthUnlocked(f.settlementMonth,'保存收入项目'))return;"
guard = (
    "if(!f.id&&f.ownerType==='CLIENT'){"
    "const linkedClient=this.clients.find(c=>String(c.id)===String(f.clientId));"
    "if(linkedClient?.archived){this.notify('归档客户不能新增回款账单');return}"
    "}"
)
marker = "linkedClient?.archived"
found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'saveReceivable')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    method = text[start:end]
    if marker in method:
        fail('saveReceivable archived-client guard already present')
    if method.count(anchor) != 1:
        fail(f'saveReceivable expected one month-lock anchor, found {method.count(anchor)}')
    patched = method.replace(anchor, guard + anchor, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveReceivable expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'exactly one app artifact must change, changed={len(changed)}')

print(
    'ARCHIVED_CLIENT_RECEIVABLE_GUARD_FINALIZE_OK: '
    'new-client-receivable=archived-denied; existing-receivable-edit=unchanged; '
    'payment-ledger=unchanged; artifact=' + changed[0][0] + ':' + changed[0][1][:12]
)
