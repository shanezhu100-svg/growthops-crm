from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

if not INDEX.is_file():
    raise SystemExit('VUE_RUNTIME_ONLY_READINESS_FAILED: dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')

class VueInventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_script = False
        self.in_style = False
        self.inline_script_blocks = 0
        self.external_script_blocks = 0
        self.inline_script_bytes = 0
        self.text_chunks = []
        self.directives = {
            'v-if': 0,
            'v-for': 0,
            'v-model': 0,
            'v-show': 0,
            'v-bind': 0,
            'v-on': 0,
            'other-v': 0,
        }
        self.current_inline_script = False

    def handle_starttag(self, tag, attrs):
        low_tag = tag.lower()
        if low_tag == 'script':
            self.in_script = True
            src = next((value for name, value in attrs if (name or '').lower() == 'src'), None)
            self.current_inline_script = src is None
            if self.current_inline_script:
                self.inline_script_blocks += 1
            else:
                self.external_script_blocks += 1
        elif low_tag == 'style':
            self.in_style = True
        for name, _ in attrs:
            low = (name or '').lower()
            if low == 'v-if' or low.startswith('v-if:'):
                self.directives['v-if'] += 1
            elif low == 'v-for' or low.startswith('v-for:'):
                self.directives['v-for'] += 1
            elif low == 'v-model' or low.startswith('v-model:'):
                self.directives['v-model'] += 1
            elif low == 'v-show' or low.startswith('v-show:'):
                self.directives['v-show'] += 1
            elif low.startswith('v-bind:') or low.startswith(':'):
                self.directives['v-bind'] += 1
            elif low.startswith('v-on:') or low.startswith('@'):
                self.directives['v-on'] += 1
            elif low.startswith('v-'):
                self.directives['other-v'] += 1

    def handle_endtag(self, tag):
        low_tag = tag.lower()
        if low_tag == 'script':
            self.in_script = False
            self.current_inline_script = False
        elif low_tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_script:
            if self.current_inline_script:
                self.inline_script_bytes += len(data.encode('utf-8'))
            return
        if self.in_style:
            return
        self.text_chunks.append(data)

parser = VueInventory()
parser.feed(html)
parser.close()

visible_text = ''.join(parser.text_chunks)
mustache_count = len(re.findall(r'\{\{.*?\}\}', visible_text, flags=re.S))
create_app_count = len(re.findall(r'\b(?:Vue\.)?createApp\s*\(', html))
mount_count = len(re.findall(r'\.mount\s*\(', html))
render_option_count = len(re.findall(r'(?<![\w$])render\s*:\s*(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*)', html))
template_option_count = len(re.findall(r'(?<![\w$])template\s*:\s*[`\'\"]', html))
compiler_markers = (
    'compileToFunction',
    'runtimeCompiler',
    'Vue.compile',
)
compiler_marker_hits = sum(html.count(marker) for marker in compiler_markers)

directive_total = sum(parser.directives.values())
template_surface = directive_total + mustache_count + template_option_count

# This is an audit gate, not a migration. Fail only if the parser lost contact with
# the known Vue application shape; print the actual compiler-dependent surface so a
# future runtime-only migration can be scoped from evidence rather than guesswork.
if create_app_count < 1:
    raise SystemExit('VUE_RUNTIME_ONLY_READINESS_FAILED: no createApp call found; audit baseline drifted')
if mount_count < 1:
    raise SystemExit('VUE_RUNTIME_ONLY_READINESS_FAILED: no mount call found; audit baseline drifted')
if directive_total < 1:
    raise SystemExit('VUE_RUNTIME_ONLY_READINESS_FAILED: no Vue directives found; final-template parser baseline drifted')
if parser.inline_script_blocks < 1 or parser.inline_script_bytes < 1024:
    raise SystemExit('VUE_RUNTIME_ONLY_READINESS_FAILED: inline application script baseline unexpectedly absent')

runtime_only_ready = template_surface == 0 and render_option_count >= create_app_count
print(
    'VUE_RUNTIME_ONLY_READINESS_AUDIT: '
    f'createApp={create_app_count}; mount={mount_count}; render-options={render_option_count}; '
    f'template-options={template_option_count}; directives={directive_total}; '
    + ','.join(f'{name}={count}' for name, count in parser.directives.items()) + '; '
    f'mustache={mustache_count}; inline-script-blocks={parser.inline_script_blocks}; '
    f'inline-script-bytes={parser.inline_script_bytes}; external-script-blocks={parser.external_script_blocks}; '
    f'explicit-compiler-markers={compiler_marker_hits}; template-surface={template_surface}; '
    f'runtime-only-ready={str(runtime_only_ready).lower()}'
)
