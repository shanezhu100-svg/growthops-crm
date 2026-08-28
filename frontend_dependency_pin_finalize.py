from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

VUE_OLD = 'https://unpkg.com/vue@3/dist/vue.global.js'
VUE_NEW = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'
TAILWIND_OLD = 'https://cdn.tailwindcss.com'
TAILWIND_NEW = 'https://cdn.tailwindcss.com/3.4.17'

if not INDEX.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
for label, old, new in (
    ('Vue', VUE_OLD, VUE_NEW),
    ('Tailwind', TAILWIND_OLD, TAILWIND_NEW),
):
    old_count = html.count(old)
    new_count = html.count(new)
    if old_count != 1:
        raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: unexpected unpinned {label} count={old_count}')
    if new_count != 0:
        raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: pinned {label} unexpectedly present before finalize count={new_count}')
    html = html.replace(old, new, 1)

INDEX.write_text(html, encoding='utf-8')
print('FRONTEND_DEPENDENCY_PIN_FINALIZE_OK: vue=3.5.41-exact; tailwind-play=3.4.17-exact; floating-cdn-entrypoints=removed')
