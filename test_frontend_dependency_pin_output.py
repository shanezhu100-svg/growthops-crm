from pathlib import Path
import hashlib
import re

root = Path(__file__).resolve().parent
index = root / 'dist' / 'index.html'
tailwind_css = root / 'dist' / 'tailwind.css'

if not index.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/index.html missing')

html = index.read_text(encoding='utf-8')
vue_pinned = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'
vue_unpinned = 'https://unpkg.com/vue@3/dist/vue.global.js'
tailwind_play = 'https://cdn.tailwindcss.com'
tailwind_static_tag = '<link rel="stylesheet" href="/tailwind.css" />'

if html.count(vue_pinned) != 1:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: expected exactly one pinned Vue URL, found {html.count(vue_pinned)}')
if vue_unpinned in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: major-only Vue CDN URL remains')
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
if 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: XLSX exact-version dependency drifted')
if 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Font Awesome exact-version dependency drifted')

# Static-Tailwind readiness: the build-time scanner can discover complete utility
# tokens that appear as literals anywhere in the final HTML/JS payload, including
# full class strings selected through Vue :class bindings. It cannot safely discover
# a utility assembled from runtime fragments (for example 'bg-' + color or
# `text-${tone}-700`). Fail closed if those patterns appear.
bound_class_pattern = re.compile(r'(?:^|\s)(?::class|v-bind:class)\s*=\s*(["\'])(.*?)\1', re.DOTALL)
bound_class_expressions = [match.group(2) for match in bound_class_pattern.finditer(html)]
if not bound_class_expressions:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: no Vue bound class expressions found; readiness parser may have drifted')

utility_families = (
    'bg', 'text', 'border', 'ring', 'from', 'via', 'to', 'shadow', 'fill', 'stroke',
    'outline', 'decoration', 'accent', 'caret', 'divide', 'placeholder', 'grid-cols',
    'grid-rows', 'col-span', 'row-span', 'z', 'w', 'h', 'min-w', 'min-h', 'max-w',
    'max-h', 'p', 'px', 'py', 'pt', 'pr', 'pb', 'pl', 'm', 'mx', 'my', 'mt', 'mr',
    'mb', 'ml', 'gap', 'gap-x', 'gap-y', 'space-x', 'space-y', 'translate-x',
    'translate-y', 'scale', 'rotate', 'skew-x', 'skew-y', 'duration', 'delay', 'ease',
    'opacity', 'rounded', 'font', 'tracking', 'leading', 'basis', 'order', 'flex',
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
        raise SystemExit(
            'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Vue :class constructs Tailwind utility fragments at runtime; '
            'use complete literal class names or an explicit static safelist'
        )
for pattern in fragment_concat_patterns:
    if pattern.search(html):
        raise SystemExit(
            'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: runtime Tailwind utility-fragment construction found in final payload'
        )

css_sha = hashlib.sha256(css_bytes).hexdigest()
print(
    'FRONTEND_DEPENDENCY_PIN_OUTPUT_OK: vue=3.5.41; tailwind=static-3.4.17; '
    'xlsx=0.18.5; font-awesome=6.5.2; play-cdn=absent; '
    f'tailwind-css-bytes={len(css_bytes)}; tailwind-css-sha256={css_sha}; '
    f'static-tailwind-readiness=true; bound-class-expressions={len(bound_class_expressions)}'
)
