from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
EXPECTED = '<i :class="[alertStyle(item.typeKey).icon, alertStyle(item.typeKey).text]"></i>'
FORBIDDEN = '<i :class="alertStyle(item.typeKey).icon" :class="alertStyle(item.typeKey).text"></i>'


def fail(message: str) -> None:
    raise SystemExit('VUE_DUPLICATE_ATTRIBUTE_OUTPUT_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
if html.count(EXPECTED) != 1:
    fail(f'normalized alert icon binding drifted: {html.count(EXPECTED)}')
if FORBIDDEN in html:
    fail('reviewed duplicate :class anchor remains')


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
                self.duplicates.append((tag, key, line, column))
            seen.add(key)

    def handle_starttag(self, tag, attrs):
        self._check(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._check(tag, attrs)


guard = DuplicateAttributeGuard()
guard.feed(html)
guard.close()
if guard.duplicates:
    sample = ', '.join(f'{tag}[{name}]@{line}:{column}' for tag, name, line, column in guard.duplicates[:12])
    fail('duplicate HTML/Vue attributes remain: ' + sample)

print(
    'VUE_DUPLICATE_ATTRIBUTE_OUTPUT_OK: '
    'reviewed-alert-binding=class-array; duplicate-attributes=0; parser=HTMLParser'
)
