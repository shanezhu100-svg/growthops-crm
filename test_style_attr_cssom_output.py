from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP = DIST / 'app'
CSS = APP / 'app-dynamic-style.css'
VERCEL = ROOT / 'vercel.json'
EXPECTED_CSS_SHA = '5ca8e8396b3686a91c447423cd0b16cdee93eb9e0ba025a1672c6bb2d3463007'
EXPECTED_CSS_BYTES = 1198


def fail(message: str) -> None:
    raise SystemExit('STYLE_ATTR_CSSOM_OUTPUT_FAILED: ' + message)


if not INDEX.is_file() or not CSS.is_file():
    fail('required final artifacts missing')
html = INDEX.read_text(encoding='utf-8')
css_bytes = CSS.read_bytes()
if len(css_bytes) != EXPECTED_CSS_BYTES:
    fail(f'dynamic CSS size drift: expected={EXPECTED_CSS_BYTES}; actual={len(css_bytes)}')
actual_css_sha = hashlib.sha256(css_bytes).hexdigest()
if actual_css_sha != EXPECTED_CSS_SHA:
    fail(f'dynamic CSS hash drift: expected={EXPECTED_CSS_SHA}; actual={actual_css_sha}')
css = css_bytes.decode('utf-8')
for marker in (
    '[data-growthops-credential-v6-gate="pending"]',
    'pointer-events: none;',
    '.growthops-clipboard-fallback',
    'position: fixed;',
    'opacity: 0;',
    '.growthops-roas-progress',
    '.growthops-roas-progress.bg-blue-600::-webkit-progress-value',
    '.growthops-roas-progress.bg-slate-950::-webkit-progress-value',
):
    if marker not in css:
        fail('dynamic CSS marker missing: ' + marker)

class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.literal_style_attrs = 0
        self.bound_style_attrs = 0
        self.progress = []
        self.dynamic_css_links = 0
    def handle_starttag(self, tag, attrs):
        amap = {str(k).lower(): v for k, v in attrs if k}
        for name, _ in attrs:
            low=(name or '').lower()
            if low == 'style': self.literal_style_attrs += 1
            elif low in (':style','v-bind:style'): self.bound_style_attrs += 1
        if tag.lower() == 'progress':
            self.progress.append(amap)
        if tag.lower() == 'link' and amap.get('href') == '/app/app-dynamic-style.css':
            if (amap.get('rel') or '').lower() != 'stylesheet':
                fail('dynamic CSS link has wrong rel')
            self.dynamic_css_links += 1

parser=Inventory(); parser.feed(html); parser.close()
if parser.literal_style_attrs != 0 or parser.bound_style_attrs != 0:
    fail(f'HTML style attributes remain: literal={parser.literal_style_attrs}; bound={parser.bound_style_attrs}')
if re.search(r'\bv-show\s*=', html, flags=re.I):
    fail('v-show remains and may write style.display at runtime')
if parser.dynamic_css_links != 1:
    fail(f'dynamic CSS link count drifted: {parser.dynamic_css_links}')
if len(parser.progress) != 1:
    fail(f'ROAS progress element count drifted: {len(parser.progress)}')
progress=parser.progress[0]
if progress.get(':value') != 'bar.width' or progress.get('max') != '100' or progress.get(':class') != 'bar.className':
    fail('ROAS progress binding drifted')
if 'growthops-roas-progress' not in (progress.get('class') or '').split():
    fail('ROAS progress class missing')

app_text=''
for path in sorted(APP.glob('app-inline-*.js')):
    app_text += '\n' + path.read_text(encoding='utf-8')
for label, pattern in (
    ('dot-style', r'\.style\s*(?:\.|\[)'),
    ('setAttribute-style', r'\.setAttribute\s*\(\s*["\']style["\']'),
    ('cssText', r'\.cssText\b'),
    ('setProperty', r'\.style\.setProperty\s*\('),
):
    if re.search(pattern, app_text, flags=re.I):
        fail('first-party CSSOM style sink remains: ' + label)
if "data-growthops-credential-v6-gate','pending'" not in app_text or "data-growthops-credential-v6-gate','ready'" not in app_text:
    fail('credential gate data-state transitions missing')
if "className='growthops-clipboard-fallback'" not in app_text:
    fail('clipboard fallback class migration missing')

cfg=json.loads(VERCEL.read_text(encoding='utf-8'))
csp=''
for rule in cfg.get('headers',[]):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers',[]):
            if item.get('key') == 'Content-Security-Policy': csp=item.get('value','')
if "style-src-attr 'none'" not in csp or "'unsafe-inline'" in csp:
    fail('CSP must deny style attributes and contain no unsafe-inline')

print(
    'STYLE_ATTR_CSSOM_OUTPUT_OK: html-style-attrs=0; vue-bound-style=0; v-show=0; '
    'first-party-cssom=0; roas=progress; credential=data-state-css; clipboard=class-css; '
    f'dynamic-css={actual_css_sha}/{len(css_bytes)}B; style-src-attr=none; unsafe-inline=absent'
)
