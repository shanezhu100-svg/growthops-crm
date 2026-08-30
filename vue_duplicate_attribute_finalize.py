from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

OLD = '<i :class="alertStyle(item.typeKey).icon" :class="alertStyle(item.typeKey).text"></i>'
NEW = '<i :class="[alertStyle(item.typeKey).icon, alertStyle(item.typeKey).text]"></i>'


def fail(message: str) -> None:
    raise SystemExit('VUE_DUPLICATE_ATTRIBUTE_FINALIZE_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
old_count = html.count(OLD)
new_count = html.count(NEW)
if old_count != 1:
    fail(f'expected exactly one reviewed duplicate :class anchor, found {old_count}')
if new_count != 0:
    fail(f'normalized anchor unexpectedly already present: {new_count}')

html = html.replace(OLD, NEW, 1)
if OLD in html or html.count(NEW) != 1:
    fail('duplicate-class normalization postcondition failed')

INDEX.write_text(html, encoding='utf-8')
print(
    'VUE_DUPLICATE_ATTRIBUTE_FINALIZE_OK: '
    'alert-icon=:class-array; duplicate-binding=removed; semantic-class-pair=preserved'
)
