from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RENEWAL_INTEGRITY_GUARD_FINALIZE_FAILED: ' + message)


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

old = "if(item.isStandalone){const a=this.standaloneAlerts.find(a=>String(a.id)===String(item.id));if(a)a.dueDate=newDue}else{"
new = "if(item.isStandalone){const a=this.standaloneAlerts.find(a=>String(a.id)===String(item.id));if(!a){this.notify('该提醒已不存在，请刷新页面后重试');return}a.dueDate=newDue}else{"

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'saveRenewal')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if '该提醒已不存在' in source:
        fail('saveRenewal already contains standalone stale-target guard')
    if source.count(old) != 1:
        fail(f'saveRenewal standalone anchor count={source.count(old)}')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveRenewal expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected one changed artifact, found {len(changed)}')

print(
    'RENEWAL_INTEGRITY_GUARD_FINALIZE_OK: '
    'standalone-stale-target=denied-before-dismiss+persist+audit; existing-standalone=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
