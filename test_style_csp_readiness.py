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
if not parser.style_blocks:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: no inline style blocks found; baseline drifted')
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

cfg = json.loads(VERCEL.read_text(encoding='utf-8'))
csp = ''
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers', []):
            if item.get('key') == 'Content-Security-Policy':
                csp = item.get('value', '')
style_part = csp.split('style-src ', 1)[1].split(';', 1)[0] if 'style-src ' in csp else ''
if "'unsafe-inline'" not in style_part:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: style-src unsafe-inline already absent; readiness gate must be updated with migration')
if 'style-src-elem ' in csp or 'style-src-attr ' in csp:
    raise SystemExit('STYLE_CSP_READINESS_FAILED: split style directives already present; readiness gate must be updated with migration')

attrs_summary = ','.join(
    'none' if not attrs else '+'.join(attrs)
    for attrs in parser.style_block_attrs
)
cssom_summary = ','.join(f'{name}={count}' for name, count in cssom_counts.items())
print(
    'STYLE_CSP_READINESS_OK: '
    f'style-blocks={len(parser.style_blocks)}; style-bytes={style_bytes}; '
    f'style-block-attrs={attrs_summary}; literal-style-attrs={parser.literal_style_attrs}; '
    f'vue-bound-style={parser.bound_style_attrs}; app-cssom={cssom_summary}; '
    "style-src=current-self+unsafe-inline; split-elem-attr=pending"
)
