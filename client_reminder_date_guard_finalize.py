from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('CLIENT_REMINDER_DATE_GUARD_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    open_pos = text.find('{', start)
    depth = 0
    quote = ''
    escaped = False
    line_comment = False
    block_comment = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n': line_comment = False
            i += 1; continue
        if block_comment:
            if ch == '*' and nxt == '/': block_comment = False; i += 2; continue
            i += 1; continue
        if quote:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == quote: quote = ''
            i += 1; continue
        if ch == '/' and nxt == '/': line_comment = True; i += 2; continue
        if ch == '/' and nxt == '*': block_comment = True; i += 2; continue
        if ch in ('"', "'", '`'): quote = ch; i += 1; continue
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return start, i + 1
        i += 1
    fail(f'{name} closing brace missing')


def calendar_guard(value_name: str, notice: str) -> str:
    return (
        f"const dateMatch=/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})$/.exec({value_name}),"
        f"dateObj=dateMatch?new Date(Date.UTC(Number(dateMatch[1]),Number(dateMatch[2])-1,Number(dateMatch[3]))):null;"
        f"if(!dateMatch||dateObj.getUTCFullYear()!==Number(dateMatch[1])||dateObj.getUTCMonth()!==Number(dateMatch[2])-1||dateObj.getUTCDate()!==Number(dateMatch[3]))"
        f"{{this.notify('{notice}');return}}"
    )


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

lock_old = "if(!this.assertMonthUnlocked(String(this.rechargeForm.date||this.localDateKey()).slice(0,7),'登记广告充值'))return;"
lock_new = (
    "const rechargeDate=String(this.rechargeForm.date||this.localDateKey());"
    + calendar_guard('rechargeDate', '请输入有效的充值日期')
    + "if(!this.assertMonthUnlocked(rechargeDate.slice(0,7),'登记广告充值'))return;"
)
row_old = "date:this.rechargeForm.date||this.localDateKey()"
row_new = "date:rechargeDate"

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'saveRecharge')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if '请输入有效的充值日期' in source:
        fail('saveRecharge already contains calendar date guard')
    if source.count(lock_old) != 1:
        fail(f'saveRecharge lock/date anchor count={source.count(lock_old)}')
    if source.count(row_old) != 1:
        fail(f'saveRecharge persisted date anchor count={source.count(row_old)}')
    patched = source.replace(lock_old, lock_new, 1).replace(row_old, row_new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveRecharge expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected one changed artifact, found {len(changed)}')

print(
    'CLIENT_REMINDER_DATE_GUARD_FINALIZE_OK: '
    'recharge=yyyy-mm-dd+calendar-valid-before-month-lock; empty=local-default; leap-day=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
