from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
VERCEL = ROOT / 'vercel.json'
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]

if not INDEX.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: dist/index.html missing')
if not VERCEL.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: vercel.json missing')
if not VUE_ASSET.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: compiler-inclusive Vue asset missing')
if not all(path.is_file() for path in APP_FILES):
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: externalized app script inventory incomplete')

html = INDEX.read_text(encoding='utf-8')

class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline_scripts = 0
        self.external_scripts = []
        self.vue_directives = 0
        self.vue_events = 0
        self.vue_bindings = 0
        self.vue_loops = 0
        self.vue_conditionals = 0

    def handle_starttag(self, tag, attrs):
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
            src = dict(attrs).get('src')
            if src:
                self.external_scripts.append(src)
            else:
                self.inline_scripts += 1

parser = Inventory()
parser.feed(html)
parser.close()

app_blocks = [path.read_text(encoding='utf-8') for path in APP_FILES]
app_js = '\n'.join(app_blocks)
app_bytes = sum(len(block.encode('utf-8')) for block in app_blocks)
interpolations = len(re.findall(r'\{\{[^{}]+\}\}', html))
create_app_calls = len(re.findall(r'\b(?:Vue\.)?createApp\s*\(', app_js))
mount_calls = len(re.findall(r'\.mount\s*\(', app_js))

dynamic_code_patterns = {
    'eval': re.compile(r'(?<![\w$.])eval\s*\('),
    'new-function': re.compile(r'\bnew\s+Function\s*\('),
    'function-constructor': re.compile(r'(?<![\w$.])Function\s*\('),
}
found_dynamic = [name for name, pattern in dynamic_code_patterns.items() if pattern.search(app_js)]
if found_dynamic:
    raise SystemExit(
        'VUE_RUNTIME_CSP_READINESS_FAILED: app-owned JS uses dynamic-code primitive(s): '
        + ','.join(found_dynamic)
    )

if parser.inline_scripts != 0:
    raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: inline script blocks remain: {parser.inline_scripts}')
if '/vendor/vue-3.5.41.global.js' not in parser.external_scripts:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: expected same-origin Vue global asset missing')
for idx in range(1, 4):
    src = f'/app/app-inline-{idx:02d}.js'
    if parser.external_scripts.count(src) != 1:
        raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: app script reference drifted: ' + src)
if parser.vue_directives < 1 or interpolations < 1:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: Vue DOM-template markers missing; inventory baseline drifted')
if app_bytes < 250_000:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: externalized application controller inventory unexpectedly small')
if create_app_calls < 1 or mount_calls < 1:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: Vue createApp/mount bootstrap not found')

cfg = json.loads(VERCEL.read_text(encoding='utf-8'))
csp = ''
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers', []):
            if item.get('key') == 'Content-Security-Policy':
                csp = item.get('value', '')
if "'unsafe-inline'" in csp.split('script-src ', 1)[1].split(';', 1)[0]:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: script-src unsafe-inline remains after app JS externalization')
if "'unsafe-eval'" not in csp:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: unsafe-eval already absent; Vue compiler migration must be reviewed separately')

print(
    'VUE_RUNTIME_CSP_READINESS_OK: '
    f'directives={parser.vue_directives}; events={parser.vue_events}; bindings={parser.vue_bindings}; '
    f'loops={parser.vue_loops}; conditionals={parser.vue_conditionals}; interpolations={interpolations}; '
    f'inline-scripts=0; app-script-files={len(APP_FILES)}; app-bytes={app_bytes}; '
    f'createApp={create_app_calls}; mount={mount_calls}; app-dynamic-code=0; '
    'vue-build=compiler-inclusive-global; unsafe-eval=current-vue-compiler-boundary'
)
