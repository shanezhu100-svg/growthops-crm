from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_PAYMENT_DATE_GUARD_FINALIZE_FAILED: ' + message)


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

old = "if(!Number.isFinite(amount)||amount<=0){this.notify('请输入有效回款金额');return}if(!this.assertMonthUnlocked(String(payDate).slice(0,7),'登记该到账日期的回款'))return;"
new = (
    "if(!Number.isFinite(amount)||amount<=0){this.notify('请输入有效回款金额');return}"
    "const payDateMatch=/^(\\d{4})-(\\d{2})-(\\d{2})$/.exec(String(payDate));"
    "if(!payDateMatch){this.notify('请输入有效到账日期');return}"
    "const payDateYear=Number(payDateMatch[1]),payDateMonth=Number(payDateMatch[2]),payDateDay=Number(payDateMatch[3]),"
    "payDateCheck=new Date(Date.UTC(payDateYear,payDateMonth-1,payDateDay));"
    "if(payDateCheck.getUTCFullYear()!==payDateYear||payDateCheck.getUTCMonth()!==payDateMonth-1||payDateCheck.getUTCDate()!==payDateDay){this.notify('请输入有效到账日期');return}"
    "if(!this.assertMonthUnlocked(String(payDate).slice(0,7),'登记该到账日期的回款'))return;"
)

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
    if 'payDateMatch=' in source or '请输入有效到账日期' in source:
        fail('saveReceivablePayment already contains payment-date guard')
    if source.count(old) != 1:
        fail(f'saveReceivablePayment date-validation anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveReceivablePayment expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'RECEIVABLE_PAYMENT_DATE_GUARD_FINALIZE_OK: '
    'date=yyyy-mm-dd+calendar-valid; malformed+impossible=denied-before-month-lock+persist; '
    'empty=local-date-default; leap-day=calendar-validated; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
