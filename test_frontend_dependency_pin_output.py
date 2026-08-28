from pathlib import Path
import re

root = Path(__file__).resolve().parent
index = root / 'dist' / 'index.html'

if not index.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/index.html missing')

html = index.read_text(encoding='utf-8')
vue_pinned = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'
vue_unpinned = 'https://unpkg.com/vue@3/dist/vue.global.js'
tailwind_pinned = 'https://cdn.tailwindcss.com/3.4.17'
tailwind_unpinned = 'https://cdn.tailwindcss.com'

if html.count(vue_pinned) != 1:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: expected exactly one pinned Vue URL, found {html.count(vue_pinned)}')
if vue_unpinned in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: major-only Vue CDN URL remains')
if html.count(tailwind_pinned) != 1:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: expected exactly one pinned Tailwind Play CDN URL, found {html.count(tailwind_pinned)}')
if tailwind_unpinned in html.replace(tailwind_pinned, '', 1):
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: floating Tailwind Play CDN URL remains')
if 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: XLSX exact-version dependency drifted')
if 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Font Awesome exact-version dependency drifted')

# Static-Tailwind readiness: the future build-time scanner can discover complete
# utility tokens that appear as literals anywhere in this final HTML/JS payload,
# including full class strings selected through Vue :class bindings. What it cannot
# safely discover is a utility assembled from fragments at runtime (for example
# 'bg-' + color or `text-${tone}-700`). Fail closed if those patterns appear.
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
            'use complete literal class names or an explicit static safelist before removing Tailwind Play CDN'
        )

# Also scan script data/helpers outside :class attributes because a bound class may
# reference a computed property whose implementation lives elsewhere in the payload.
for pattern in fragment_concat_patterns:
    if pattern.search(html):
        raise SystemExit(
            'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: runtime Tailwind utility-fragment construction found in final payload'
        )

print(
    'FRONTEND_DEPENDENCY_PIN_OUTPUT_OK: vue=3.5.41; tailwind-play=3.4.17; '
    'xlsx=0.18.5; font-awesome=6.5.2; floating-cdn-entrypoints=absent; '
    f'static-tailwind-readiness=true; bound-class-expressions={len(bound_class_expressions)}'
)
