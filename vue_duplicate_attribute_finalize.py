from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

ICON = 'alertStyle(item.typeKey).icon'
TEXT = 'alertStyle(item.typeKey).text'
RULES = (
    (
        '<i :class="' + ICON + '" :class="' + TEXT + '">',
        '<i :class="[' + ICON + ', ' + TEXT + ']">',
        'plain-alert-icon',
    ),
    (
        '<i :class="' + ICON + '" class="text-sm" :class="' + TEXT + '">',
        '<i class="text-sm" :class="[' + ICON + ', ' + TEXT + ']">',
        'text-sm-alert-icon',
    ),
)


def fail(message: str) -> None:
    raise SystemExit('VUE_DUPLICATE_ATTRIBUTE_FINALIZE_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
for old, new, label in RULES:
    old_count = html.count(old)
    new_count = html.count(new)
    if old_count != 1:
        fail(f'{label}: expected exactly one reviewed duplicate :class anchor, found {old_count}')
    if new_count != 0:
        fail(f'{label}: normalized anchor unexpectedly already present: {new_count}')

for old, new, label in RULES:
    html = html.replace(old, new, 1)
    if old in html or html.count(new) != 1:
        fail(f'{label}: duplicate-class normalization postcondition failed')

INDEX.write_text(html, encoding='utf-8')
print(
    'VUE_DUPLICATE_ATTRIBUTE_FINALIZE_OK: '
    'alert-icons=2-reviewed; dynamic-class=array; static-text-sm=preserved; '
    'duplicate-bindings=removed; semantic-class-pairs=preserved'
)
