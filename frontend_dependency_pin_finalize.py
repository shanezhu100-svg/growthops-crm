from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

OLD = 'https://unpkg.com/vue@3/dist/vue.global.js'
NEW = 'https://unpkg.com/vue@3.5.41/dist/vue.global.js'

if not INDEX.is_file():
    raise SystemExit('FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
old_count = html.count(OLD)
new_count = html.count(NEW)
if old_count != 1:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: unexpected unpinned Vue count={old_count}')
if new_count != 0:
    raise SystemExit(f'FRONTEND_DEPENDENCY_PIN_FINALIZE_FAILED: pinned Vue unexpectedly present before finalize count={new_count}')

html = html.replace(OLD, NEW, 1)
INDEX.write_text(html, encoding='utf-8')
print('FRONTEND_DEPENDENCY_PIN_FINALIZE_OK: vue=3.5.41-exact; unpkg-major-only=removed; tailwind-play-cdn=unchanged-known-debt')
