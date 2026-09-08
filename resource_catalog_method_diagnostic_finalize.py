from pathlib import Path
import base64
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
NAMES = (
    'saveExternalAsset', 'deleteExternalAsset',
    'saveMediaTool', 'deleteMediaTool',
    'saveReminderType', 'deleteReminderType',
)


def fail(message: str) -> None:
    raise SystemExit('RESOURCE_CATALOG_METHOD_DIAGNOSTIC_FAILED: ' + message)


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
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = ''
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    fail(f'{name} closing brace missing')


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = {name: 0 for name in NAMES}
for path in files:
    text = path.read_text(encoding='utf-8')
    for name in NAMES:
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        found[name] += 1
        start, end = bounds
        source = text[start:end].strip()
        encoded = base64.b64encode(source.encode('utf-8')).decode('ascii')
        print(f'RESOURCE_METHOD_SOURCE::{name}::{encoded}')

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected exactly once, found {count}')
print('RESOURCE_CATALOG_METHOD_DIAGNOSTIC_OK: methods=6; encoding=base64')
