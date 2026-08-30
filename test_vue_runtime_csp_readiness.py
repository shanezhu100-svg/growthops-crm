from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
VERCEL = ROOT / 'vercel.json'
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]

# Freeze the last compiler-inclusive template inventory immediately before the
# reviewed runtime-only cutover. The build is not deployable at this intermediate
# stage; downstream finalizers must replace these templates with pinned render
# functions before output verification succeeds under the eval-free CSP.
COMPILER_DEBT_BUDGET = {
    'directives': 1327,
    'events': 299,
    'bindings': 366,
    'loops': 124,
    'conditionals': 293,
    'interpolations': 709,
    'template_options': 4,
}

if not INDEX.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: dist/index.html missing')
if not VERCEL.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: vercel.json missing')
if not VUE_ASSET.is_file():
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: compiler-inclusive build-time Vue asset missing')
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
        self.vue_html = 0

    def handle_starttag(self, tag, attrs):
        for name, _ in attrs:
            low = (name or '').lower()
            if low.startswith('v-') or low.startswith('@') or low.startswith(':'):
                self.vue_directives += 1
            if low.startswith('@') or low.startswith('v-on:'):
                self.vue_events += 1
            if low.startswith(':') or low.startswith('v-bind:'):
                self.vue_bindings += 1
            if low == 'v-for': self.vue_loops += 1
            if low in ('v-if', 'v-else-if', 'v-else', 'v-show'): self.vue_conditionals += 1
            if low == 'v-html': self.vue_html += 1
        if tag.lower() == 'script':
            src = dict(attrs).get('src')
            if src: self.external_scripts.append(src)
            else: self.inline_scripts += 1

parser = Inventory(); parser.feed(html); parser.close()
app_blocks = [path.read_text(encoding='utf-8') for path in APP_FILES]
app_js = '\n'.join(app_blocks)
app_bytes = sum(len(block.encode('utf-8')) for block in app_blocks)
interpolations = len(re.findall(r'\{\{[^{}]+\}\}', html))
create_app_calls = len(re.findall(r'\b(?:Vue\.)?createApp\s*\(', app_js))
mount_calls = len(re.findall(r'\.mount\s*\(', app_js))
vue_compile_calls = len(re.findall(r'\bVue\.compile\s*\(', app_js))
template_options = len(re.findall(r'(?<![\w$])template\s*:', app_js))

for name, pattern in {
    'eval': re.compile(r'(?<![\w$.])eval\s*\('),
    'new-function': re.compile(r'\bnew\s+Function\s*\('),
    'function-constructor': re.compile(r'(?<![\w$.])Function\s*\('),
}.items():
    if pattern.search(app_js):
        raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: app-owned JS uses dynamic-code primitive: ' + name)
if parser.inline_scripts != 0:
    raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: inline script blocks remain: {parser.inline_scripts}')
if '/vendor/vue-3.5.41.global.js' not in parser.external_scripts:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: expected build-time Vue compiler asset missing before cutover')
for idx in range(1, 4):
    src = f'/app/app-inline-{idx:02d}.js'
    if parser.external_scripts.count(src) != 1:
        raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: app script reference drifted: ' + src)
if parser.vue_directives < 1 or interpolations < 1:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: Vue DOM-template markers missing; inventory baseline drifted')
if app_bytes < 250_000:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: externalized application controller inventory unexpectedly small')
if create_app_calls != 1 or mount_calls != 1:
    raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: bootstrap multiplicity drifted: createApp={create_app_calls}; mount={mount_calls}')
if parser.vue_html != 0:
    raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: v-html introduced: {parser.vue_html}')
if vue_compile_calls != 0:
    raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: explicit Vue.compile introduced: {vue_compile_calls}')

observed_debt = {
    'directives': parser.vue_directives, 'events': parser.vue_events, 'bindings': parser.vue_bindings,
    'loops': parser.vue_loops, 'conditionals': parser.vue_conditionals,
    'interpolations': interpolations, 'template_options': template_options,
}
for name, actual in observed_debt.items():
    budget = COMPILER_DEBT_BUDGET[name]
    if actual > budget:
        raise SystemExit(f'VUE_RUNTIME_CSP_READINESS_FAILED: compiler debt increased: {name}={actual}; budget={budget}')

cfg = json.loads(VERCEL.read_text(encoding='utf-8')); csp = ''
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        for item in rule.get('headers', []):
            if item.get('key') == 'Content-Security-Policy': csp = item.get('value', '')
if not csp or 'script-src ' not in csp:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: script-src missing')
script_tokens = csp.split('script-src ', 1)[1].split(';', 1)[0].split()
if script_tokens != ["'self'"] or "'unsafe-inline'" in csp or "'unsafe-eval'" in csp:
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: target CSP must already be same-origin and eval-free')

build = (ROOT / 'build.sh').read_text(encoding='utf-8')
for call in ('python3 vue_runtime_only_finalize.py', 'python3 vue_runtime_compiled_marker_finalize.py', 'python3 test_vue_runtime_only_output.py'):
    if build.count(call) != 1:
        raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: downstream runtime-only cutover gate missing: ' + call)
if not (build.index('python3 test_vue_runtime_csp_readiness.py') < build.index('python3 vue_runtime_only_finalize.py') < build.index('python3 vue_runtime_compiled_marker_finalize.py') < build.index('python3 test_vue_runtime_only_output.py')):
    raise SystemExit('VUE_RUNTIME_CSP_READINESS_FAILED: runtime-only cutover order drifted')

print(
    'VUE_RUNTIME_CSP_READINESS_OK: '
    f'directives={parser.vue_directives}/{COMPILER_DEBT_BUDGET["directives"]}; events={parser.vue_events}/{COMPILER_DEBT_BUDGET["events"]}; '
    f'bindings={parser.vue_bindings}/{COMPILER_DEBT_BUDGET["bindings"]}; loops={parser.vue_loops}/{COMPILER_DEBT_BUDGET["loops"]}; '
    f'conditionals={parser.vue_conditionals}/{COMPILER_DEBT_BUDGET["conditionals"]}; interpolations={interpolations}/{COMPILER_DEBT_BUDGET["interpolations"]}; '
    f'template-options={template_options}/{COMPILER_DEBT_BUDGET["template_options"]}; inline-scripts=0; app-script-files={len(APP_FILES)}; '
    f'app-bytes={app_bytes}; createApp={create_app_calls}; mount={mount_calls}; app-dynamic-code=0; v-html={parser.vue_html}; Vue.compile={vue_compile_calls}; '
    'pre-cutover-compiler=build-time-only; target-csp=self-only+eval-free; downstream-runtime-cutover=required; debt-budget=frozen'
)

# Preserve independent compiler/runtime feasibility evidence before the compiler
# asset is removed later in the same portable build.
import test_vue_precompile_feasibility  # noqa: F401,E402
import test_vue_precompiled_render_artifact  # noqa: F401,E402
import test_vue_runtime_only_asset  # noqa: F401,E402
