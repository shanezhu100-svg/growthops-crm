from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_GENERATION_AMOUNT_GUARD_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\s*\()', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).rfind(name)
    paren = text.find('(', start + len(name))
    depth = 0; quote = ''; escaped = False; line_comment = False; block_comment = False
    i = paren
    while i < len(text):
        ch = text[i]; nxt = text[i + 1] if i + 1 < len(text) else ''
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
        if ch == '(': depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0: break
        i += 1
    if depth != 0: fail(f'{name} parameter list unmatched')
    open_pos = i + 1
    while open_pos < len(text) and text[open_pos].isspace(): open_pos += 1
    if open_pos >= len(text) or text[open_pos] != '{': fail(f'{name} opening brace missing')
    depth = 0; quote = ''; escaped = False; line_comment = False; block_comment = False
    i = open_pos
    while i < len(text):
        ch = text[i]; nxt = text[i + 1] if i + 1 < len(text) else ''
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


if not APP_DIR.is_dir(): fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files: fail('no app-inline JS')

old = "if(!client||client.archived||!month||(client.billingMode||'FULL_MONTH')==='MANUAL'||Number(client.monthlyFee||0)<=0||this.isMonthLocked(month))return 0;"
new = "const monthlyFee=Number(client&&client.monthlyFee||0);if(!client||client.archived||!month||(client.billingMode||'FULL_MONTH')==='MANUAL'||!Number.isFinite(monthlyFee)||monthlyFee<=0||this.isMonthLocked(month))return 0;"

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'createReceivableForClientMonth')
    if bounds is None: continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if 'const monthlyFee=Number(client&&client.monthlyFee||0);' in source:
        fail('monthly fee guard already present')
    if source.count(old) != 1:
        fail(f'monthly fee guard anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1: fail(f'createReceivableForClientMonth expected once, found {found}')
if len(changed) != 1: fail(f'expected one changed artifact, found {len(changed)}')
print('RECEIVABLE_GENERATION_AMOUNT_GUARD_FINALIZE_OK: monthlyFee=finite-positive-before-generation; calculated-amount=unchanged-for-next-red; artifact=' + ','.join(f'{n}:{h[:12]}' for n,h in changed))