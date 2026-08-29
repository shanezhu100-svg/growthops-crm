from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
VERCEL = ROOT / 'vercel.json'
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'

if not INDEX.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: dist/index.html missing')
if not VERCEL.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: vercel.json missing')
if not VUE_ASSET.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: compiler-inclusive Vue asset missing')

html = INDEX.read_text(encoding='utf-8')

class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline_scripts = []
        self.external_scripts = []
        self._capture_script = False
        self._script_buf = []
        self.vue_directives = 0
        self.vue_events = 0
        self.vue_bindings = 0
        self.vue_loops = 0
        self.vue_conditionals = 0
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if attr_map.get('id'):
            self.ids.add(attr_map['id'])
        for name, _ in attrs:
            low = (name or '').lower()
            if low.startswith('v-') or low.startswith('@') or low.startswith(':'):
                self.vue_directives += 1
            if low.startswith('@') or low.startswith('v-on:'):
                self.vue_events += 1
            if low.startswith(':') or low.startswith('v-bind:'):
                self.vue_bindings += 1
            if low == 'v-for':
                self.vue_loops += 1
            if low in ('v-if', 'v-else-if', 'v-else', 'v-show'):
                self.vue_conditionals += 1
        if tag.lower() == 'script':
            src = attr_map.get('src')
            if src:
                self.external_scripts.append(src)
            else:
                self._capture_script = True
                self._script_buf = []

    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self._capture_script:
            self.inline_scripts.append(''.join(self._script_buf))
            self._capture_script = False
            self._script_buf = []

    def handle_data(self, data):
        if self._capture_script:
            self._script_buf.append(data)

parser = Inventory()
parser.feed(html)
parser.close()

inline_js = '\n'.join(parser.inline_scripts)
inline_bytes = sum(len(block.encode('utf-8')) for block in parser.inline_scripts)
interpolations = len(re.findall(r'\{\{[^{}]+\}\}', html))
create_app_calls = len(re.findall(r'\b(?:Vue\.)?createApp\s*\(', inline_js))
mount_calls = len(re.findall(r'\.mount\s*\(', inline_js))

# App-owned JavaScript must not introduce its own dynamic-code primitive. Vue's
# compiler implementation lives in the separately hash-pinned vendor asset and is
# intentionally inventoried, not scanned as application code here.
dynamic_code_patterns = {
    'eval': re.compile(r'(?<![\w$.])eval\s*\('),
    'new-function': re.compile(r'\bnew\s+Function\s*\('),
    'function-constructor': re.compile(r'(?<![\w$.])Function\s*\('),
}
found_dynamic = [name for name, pattern in dynamic_code_patterns.items() if pattern.search(inline_js)]
if found_dynamic:
    raise SystemExit(
        'VUE_RUNTIME_CSP_READINESS_FAILED: app-owned inline JS uses dynamic-code primitive(s): '
        + ','.join(found_dynamic)
    )

if '/vendor/vue-3.5.41.global.js' not in parser.external_scripts:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: expected same-origin Vue global asset missing')
if parser.vue_directives < 1 or interpolations < 1:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: Vue DOM-template markers missing; inventory baseline drifted')
if not parser.inline_scripts or inline_bytes < 1024:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: inline application controller inventory unexpectedly empty')
if create_app_calls < 1 or mount_calls < 1:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: Vue createApp/mount bootstrap not found')

cfg = json.loads(VERCEL.read_text(encoding='utf-8'))
csp = ''
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers', []):
            if item.get('key') == 'Content-Security-Policy':
                csp = item.get('value', '')
if "'unsafe-eval'" not in csp:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: unsafe-eval already absent; readiness gate must be updated with migration')

print(
    'VUE_RUNTIME_CSP_READINESS_OK: '
    f'directives={parser.vue_directives}; events={parser.vue_events}; bindings={parser.vue_bindings}; '
    f'loops={parser.vue_loops}; conditionals={parser.vue_conditionals}; interpolations={interpolations}; '
    f'inline-scripts={len(parser.inline_scripts)}; inline-bytes={inline_bytes}; '
    f'createApp={create_app_calls}; mount={mount_calls}; app-dynamic-code=0; '
    'vue-build=compiler-inclusive-global; unsafe-eval=current-vue-compiler-boundary'
)
