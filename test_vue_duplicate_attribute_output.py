from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
ICON = 'alertStyle(item.typeKey).icon'
TEXT = 'alertStyle(item.typeKey).text'
EXPECTED = (
    '<i :class="[' + ICON + ', ' + TEXT + ']">',
    '<i class="text-sm" :class="[' + ICON + ', ' + TEXT + ']">',
)
FORBIDDEN = (
    '<i :class="' + ICON + '" :class="' + TEXT + '">',
    '<i :class="' + ICON + '" class="text-sm" :class="' + TEXT + '">',
)


def fail(message: str) -> None:
    raise SystemExit('VUE_DUPLICATE_ATTRIBUTE_OUTPUT_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
for marker in EXPECTED:
    if html.count(marker) != 1:
        fail(f'normalized alert icon binding drifted: marker={marker}; count={html.count(marker)}')
for marker in FORBIDDEN:
    if marker in html:
        fail('reviewed duplicate :class anchor remains: ' + marker)


class DuplicateAttributeGuard(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.duplicates = []

    def _check(self, tag, attrs):
        seen = set()
        for name, _value in attrs:
            key = (name or '').lower()
            if key in seen:
                line, column = self.getpos()
                raw = (self.get_starttag_text() or '').replace('\n', ' ').strip()
                if len(raw) > 360:
                    raw = raw[:357] + '...'
                self.duplicates.append((tag, key, line, column, raw))
            seen.add(key)

    def handle_starttag(self, tag, attrs):
        self._check(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._check(tag, attrs)


guard = DuplicateAttributeGuard()
guard.feed(html)
guard.close()
if guard.duplicates:
    sample = ' | '.join(
        f'{tag}[{name}]@{line}:{column} tag={raw}'
        for tag, name, line, column, raw in guard.duplicates[:12]
    )
    fail('duplicate HTML/Vue attributes remain: ' + sample)

print(
    'VUE_DUPLICATE_ATTRIBUTE_OUTPUT_OK: '
    'reviewed-alert-bindings=2-class-arrays; duplicate-attributes=0; parser=HTMLParser'
)
