from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
VERCEL = ROOT / 'vercel.json'
APP_DIR = ROOT / 'dist' / 'app'

if not INDEX.is_file():
    raise SystemExit('STYLE_CSP_READINESS_FAILED: dist/index.html missing')
if not VERCEL.is_file():
    raise SystemExit('STYLE_CSP_READINESS_FAILED: vercel.json missing')

html = INDEX.read_text(encoding='utf-8')

class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.style_blocks = []
        self.style_block_attrs = []
        self.literal_style_attrs = 0
        self.bound_style_attrs = 0
        self._capture_style = False
        self._style_buf = []

    def handle_starttag(self, tag, attrs):
        low_tag = tag.lower()
        if low_tag == 'style':
            self.style_block_attrs.append(tuple((name or '').lower() for name, _ in attrs))
            self._capture_style = True
            self._style_buf = []
        for name, _ in attrs:
            low = (name or '').lower()
            if low == 'style':
                self.literal_style_attrs += 1
            elif low in (':style', 'v-bind:style'):
                self.bound_style_attrs += 1

    def handle_endtag(self, tag):
        if tag.lower() == 'style' and self._capture_style:
            self.style_blocks.append(''.join(self._style_buf))
            self._capture_style = False
            self._style_buf = []

    def handle_data(self, data):
        if self._capture_style:
            self._style_buf.append(data)

parser = Inventory()
parser.feed(html)
parser.close()

style_bytes = sum(len(block.encode('utf-8')) for block in parser.style_blocks)
if len(parser.style_blocks) != 4:
    raise SystemExit(f'STYLE_CSP_READINESS_FAILED: expected four pre-externalization style blocks, found {len(parser.style_blocks)}')
if style_bytes < 1024:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: inline style inventory unexpectedly small')

app_text = ''
app_files = sorted(APP_DIR.glob('app-inline-*.js'))
if not app_files:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: externalized app JS inventory missing')
for path in app_files:
    app_text += '\n' + path.read_text(encoding='utf-8')

cssom_patterns = {
    'dot-style': re.compile(r'\.style\s*(?:\.|\[)'),
    'set-attribute-style': re.compile(r'\.setAttribute\s*\(\s*["\']style["\']', re.I),
    'css-text': re.compile(r'\.cssText\b'),
    'set-property': re.compile(r'\.style\.setProperty\s*\('),
}
cssom_counts = {name: len(pattern.findall(app_text)) for name, pattern in cssom_patterns.items()}
vshow_count = len(re.findall(r'\bv-show\s*=', html, flags=re.I))

cfg = json.loads(VERCEL.read_text(encoding='utf-8'))
csp = ''
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers', []):
            if item.get('key') == 'Content-Security-Policy':
                csp = item.get('value', '')

def tokens(name):
    marker = name + ' '
    if marker not in csp:
        return []
    return csp.split(marker, 1)[1].split(';', 1)[0].split()

if tokens('style-src') != ["'self'"]:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: style-src fallback must be self-only')
if tokens('style-src-elem') != ["'self'"]:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: style-src-elem must be self-only')
if tokens('style-src-attr') != ["'none'"]:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: target style-src-attr must be none before final sink removal')
if parser.literal_style_attrs != 0:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: literal style attribute appeared unexpectedly')
if parser.bound_style_attrs != 1:
    raise SystemExit(f'STYLE_CSP_READINESS_FAILED: expected one migration-source Vue bound style, found {parser.bound_style_attrs}')
if cssom_counts != {'dot-style': 8, 'set-attribute-style': 0, 'css-text': 0, 'set-property': 0}:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: migration-source CSSOM inventory drifted: ' + repr(cssom_counts))
if vshow_count != 0:
    raise SystemExit(f'STYLE_CSP_READINESS_FAILED: v-show would reintroduce runtime style.display writes: {vshow_count}')

attrs_summary = ','.join('none' if not attrs else '+'.join(attrs) for attrs in parser.style_block_attrs)
cssom_summary = ','.join(f'{name}={count}' for name, count in cssom_counts.items())
print(
    'STYLE_CSP_READINESS_OK: '
    f'pre-externalization-style-blocks={len(parser.style_blocks)}; style-bytes={style_bytes}; '
    f'style-block-attrs={attrs_summary}; literal-style-attrs={parser.literal_style_attrs}; '
    f'migration-vue-bound-style={parser.bound_style_attrs}; migration-app-cssom={cssom_summary}; '
    f'v-show={vshow_count}; target-style-src-attr=none'
)
