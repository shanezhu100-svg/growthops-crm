from pathlib import Path
import hashlib
import re
import subprocess

root = Path(__file__).resolve().parent
index = root / 'dist' / 'index.html'
tailwind_css = root / 'dist' / 'tailwind.css'
vendor_dir = root / 'dist' / 'vendor'
fa_root = vendor_dir / 'fontawesome'

if not index.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/index.html missing')

html = index.read_text(encoding='utf-8')
tailwind_play = 'https://cdn.tailwindcss.com'
tailwind_static_tag = '<link rel="stylesheet" href="/tailwind.css" />'
external_vue = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'
external_xlsx = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js'
external_fa = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css'
local_vue_tag = '<script src="/vendor/vue-3.5.41.global.js"></script>'
local_xlsx_tag = '<script src="/vendor/xlsx-0.18.5.full.min.js"></script>'
local_fa_tag = '<link rel="stylesheet" href="/vendor/fontawesome/css/all.min.css" />'
expected_vendor = {
    'vue-3.5.41.global.js': ('14625269265de97b5c344b8fcfb7136c0c9ab09f7dbadc909a4967d14eca05fb', 591450),
    'xlsx-0.18.5.full.min.js': ('c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99', 881727),
}
expected_fa = {
    'css/all.min.css': ('5ceaaba22d75b58e04150311f596306562a3e595e27ed4b1dfa451b82dda9e50', 103009),
    'webfonts/fa-brands-400.ttf': ('e28096fa75a96ac77020155ea3a6dd7312983e84115366d4cf49a0c312ec6d51', 209128),
    'webfonts/fa-brands-400.woff2': ('232c6f6a7678304f9efaa26f30b1610debc2ba9f4cd636b5e6751c8d73761b92', 117852),
    'webfonts/fa-regular-400.ttf': ('9174757efc83e072436e873c22be1663d3c103b0a16d7fb73569af4918d4d351', 67860),
    'webfonts/fa-regular-400.woff2': ('c27da6f833431da5aa295c44540bfac0fd8270ba6a3c4346427006d8a7b34b76', 25392),
    'webfonts/fa-solid-900.ttf': ('b4990d0d0c5f5d38d62e936eea120674e584c7eea8dcee38a975c0cf9a37539b', 420332),
    'webfonts/fa-solid-900.woff2': ('ae17c16afbea216707b2203ea1cf9bdb45b9bfe47d0f4ae3258ddbc6294dd02f', 156400),
    'webfonts/fa-v4compatibility.ttf': ('ff8f525fb050c5d24519ccc8f5723d85b2e51edd3f9bc6548af55aebadd4f269', 10832),
    'webfonts/fa-v4compatibility.woff2': ('c7a869faca299d15be10a01f19d0765a7c4d46d8922d9b9317235c1e4a6f0982', 4792),
}

if tailwind_play in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Tailwind Play CDN runtime remains')
if html.count(tailwind_static_tag) != 1:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: same-origin Tailwind stylesheet link must appear exactly once')
if not tailwind_css.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/tailwind.css missing')
css_bytes = tailwind_css.read_bytes()
if len(css_bytes) < 4096:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/tailwind.css unexpectedly small')
css = css_bytes.decode('utf-8')
for marker in ('.hidden{display:none}', '.flex{display:flex}', '.grid{display:grid}'):
    if marker not in css:
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: static Tailwind utility missing: ' + marker)

for external in (external_vue, external_xlsx, external_fa):
    if external in html:
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: external browser dependency remains: ' + external)
for tag in (local_vue_tag, local_xlsx_tag, local_fa_tag):
    if html.count(tag) != 1:
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: same-origin dependency tag must appear exactly once: ' + tag)

for name, (expected_sha, expected_size) in expected_vendor.items():
    path = vendor_dir / name
    if not path.is_file():
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: missing dist/vendor/' + name)
    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha or len(data) != expected_size:
        raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: vendor drift {name}; expected={expected_sha}/{expected_size}; actual={actual_sha}/{len(data)}')
    subprocess.run(['node', '--check', str(path)], check=True, stdout=subprocess.DEVNULL)

for name, (expected_sha, expected_size) in expected_fa.items():
    path = fa_root / name
    if not path.is_file():
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: missing Font Awesome output: ' + name)
    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha or len(data) != expected_size:
        raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Font Awesome drift {name}; expected={expected_sha}/{expected_size}; actual={actual_sha}/{len(data)}')
fa_css = (fa_root / 'css' / 'all.min.css').read_text(encoding='utf-8')
fa_refs = sorted(set(re.findall(r'url\((?:["\']?)(\.\./webfonts/[^)"\']+)(?:["\']?)\)', fa_css)))
if len(fa_refs) != 8:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Font Awesome CSS webfont inventory must remain 8')

# Static-Tailwind readiness: complete utility tokens must remain discoverable.
bound_class_pattern = re.compile(r'(?:^|\s)(?::class|v-bind:class)\s*=\s*(["\'])(.*?)\1', re.DOTALL)
bound_class_expressions = [match.group(2) for match in bound_class_pattern.finditer(html)]
if not bound_class_expressions:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: no Vue bound class expressions found; readiness parser may have drifted')
utility_families = (
    'bg', 'text', 'border', 'ring', 'from', 'via', 'to', 'shadow', 'fill', 'stroke', 'outline',
    'decoration', 'accent', 'caret', 'divide', 'placeholder', 'grid-cols', 'grid-rows', 'col-span',
    'row-span', 'z', 'w', 'h', 'min-w', 'min-h', 'max-w', 'max-h', 'p', 'px', 'py', 'pt',
    'pr', 'pb', 'pl', 'm', 'mx', 'my', 'mt', 'mr', 'mb', 'ml', 'gap', 'gap-x', 'gap-y',
    'space-x', 'space-y', 'translate-x', 'translate-y', 'scale', 'rotate', 'skew-x', 'skew-y',
    'duration', 'delay', 'ease', 'opacity', 'rounded', 'font', 'tracking', 'leading', 'basis', 'order', 'flex',
)
family_alt = '|'.join(re.escape(item) for item in sorted(utility_families, key=len, reverse=True))
fragment_concat_patterns = (
    re.compile(rf'["\'](?:{family_alt})-["\']\s*\+'),
    re.compile(rf'\+\s*["\'](?:{family_alt})-["\']'),
    re.compile(rf'`[^`]*\b(?:{family_alt})-\$\{{', re.DOTALL),
    re.compile(rf'`[^`]*\$\{{[^}}]+\}}-(?:{family_alt})(?:-|\b)', re.DOTALL),
)
for expression in bound_class_expressions:
    if any(pattern.search(expression) for pattern in fragment_concat_patterns):
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Vue :class constructs Tailwind utility fragments at runtime')
for pattern in fragment_concat_patterns:
    if pattern.search(html):
        raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: runtime Tailwind utility-fragment construction found in final payload')

css_sha = hashlib.sha256(css_bytes).hexdigest()
print(
    'FRONTEND_DEPENDENCY_PIN_OUTPUT_OK: vue=same-origin-3.5.41+sha256; tailwind=static-3.4.17; '
    'xlsx=same-origin-0.18.5+sha256; font-awesome=same-origin-6.5.2+sha256; browser-external-js=absent; '
    'browser-cdnjs-fontawesome=absent; '
    f'tailwind-css-bytes={len(css_bytes)}; tailwind-css-sha256={css_sha}; '
    f'static-tailwind-readiness=true; bound-class-expressions={len(bound_class_expressions)}'
)
