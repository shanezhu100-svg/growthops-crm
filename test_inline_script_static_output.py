from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP_DIR = DIST / 'app'
EXPECTED = [f'app-inline-{idx:02d}.js' for idx in range(1, 4)]

if not INDEX.is_file():
    raise SystemExit('INLINE_SCRIPT_STATIC_OUTPUT_FAILED: dist/index.html missing')

class ScriptInventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline = 0
        self.srcs = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'script':
            return
        src = dict(attrs).get('src')
        if src:
            self.srcs.append(src)
        else:
            self.inline += 1

parser = ScriptInventory()
html = INDEX.read_text(encoding='utf-8')
parser.feed(html)
parser.close()

if parser.inline != 0:
    raise SystemExit(f'INLINE_SCRIPT_STATIC_OUTPUT_FAILED: inline scripts remain: {parser.inline}')

rows = []
combined = ''
for name in EXPECTED:
    src = '/app/' + name
    if parser.srcs.count(src) != 1:
        raise SystemExit(f'INLINE_SCRIPT_STATIC_OUTPUT_FAILED: expected exactly one {src} reference')
    path = APP_DIR / name
    if not path.is_file():
        raise SystemExit(f'INLINE_SCRIPT_STATIC_OUTPUT_FAILED: missing dist/app/{name}')
    data = path.read_bytes()
    if not data.strip():
        raise SystemExit(f'INLINE_SCRIPT_STATIC_OUTPUT_FAILED: empty dist/app/{name}')
    text = data.decode('utf-8')
    combined += '\n' + text
    rows.append(f'{name}={hashlib.sha256(data).hexdigest()}/{len(data)}B')

if len(combined.encode('utf-8')) < 250_000:
    raise SystemExit('INLINE_SCRIPT_STATIC_OUTPUT_FAILED: extracted application JS unexpectedly small')
for label, pattern in (
    ('eval', r'(?<![\w$.])eval\s*\('),
    ('new Function', r'\bnew\s+Function\s*\('),
    ('Function constructor', r'(?<![\w$.])Function\s*\('),
):
    if re.search(pattern, combined):
        raise SystemExit('INLINE_SCRIPT_STATIC_OUTPUT_FAILED: app script uses dynamic code primitive: ' + label)

print('INLINE_SCRIPT_STATIC_OUTPUT_OK: ' + '; '.join(rows) + '; inline=0; app-dynamic-code=0')
