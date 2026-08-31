from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_PAYMENT_AMOUNT_GUARD_FINALIZE_FAILED: ' + message)


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

old = "const amount=Number(this.paymentForm.amount||0),payDate=this.paymentForm.date||this.localDateKey();if(amount<=0)"
new = "const amount=Number(this.paymentForm.amount||0),payDate=this.paymentForm.date||this.localDateKey();if(!Number.isFinite(amount)||amount<=0)"

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'saveReceivablePayment')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if 'Number.isFinite(amount)' in source:
        fail('saveReceivablePayment already contains finite-number guard')
    if source.count(old) != 1:
        fail(f'saveReceivablePayment amount-validation anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveReceivablePayment expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'RECEIVABLE_PAYMENT_AMOUNT_GUARD_FINALIZE_OK: '
    'amount=finite-positive; zero+negative+nan+infinity=denied-before-persist; '
    'overpayment-boundary=preserved; partial+exact=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
