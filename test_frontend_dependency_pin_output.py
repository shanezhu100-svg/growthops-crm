from pathlib import Path

root = Path(__file__).resolve().parent
index = root / 'dist' / 'index.html'

if not index.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: dist/index.html missing')

html = index.read_text(encoding='utf-8')
pinned = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'
unpinned = 'https://unpkg.com/vue@3/dist/vue.global.js'

if html.count(pinned) != 1:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: expected exactly one pinned Vue URL, found {html.count(pinned)}')
if unpinned in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: major-only Vue CDN URL remains')
if 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: XLSX exact-version dependency drifted')
if 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css' not in html:
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_OUTPUT_FAILED: Font Awesome exact-version dependency drifted')

print('FRONTEND_DEPENDENCY_PIN_OUTPUT_OK: vue=3.5.41; xlsx=0.18.5; font-awesome=6.5.2; major-only-vue=absent')
