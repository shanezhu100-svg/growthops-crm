from pathlib import Path

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

print('FRONTEND_DEPENDENCY_PIN_OUTPUT_OK: vue=3.5.41; tailwind-play=3.4.17; xlsx=0.18.5; font-awesome=6.5.2; floating-cdn-entrypoints=absent')
