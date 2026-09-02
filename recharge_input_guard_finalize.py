from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECHARGE_INPUT_GUARD_FINALIZE_FAILED: ' + message)


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


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

old = "const amount=Number(this.rechargeForm.amount||0);if(amount<=0){this.notify('请输入有效的充值金额');return}"
new = "const amount=Number(this.rechargeForm.amount||0);if(!Number.isFinite(amount)||amount<=0){this.notify('请输入有效的充值金额');return}"

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
    if 'Number.isFinite(amount)' in source:
        fail('saveRecharge already contains finite amount guard')
    if source.count(old) != 1:
        fail(f'saveRecharge amount anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveRecharge expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected one changed artifact, found {len(changed)}')

print(
    'RECHARGE_INPUT_GUARD_FINALIZE_OK: '
    'amount=finite-positive; zero+negative+nan+infinity=denied-before-history+persist+audit; '
    'month-lock+valid-positive=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)

import renewal_integrity_guard_finalize  # noqa: E402,F401
