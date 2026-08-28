from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

if not INDEX.is_file():
    raise SystemExit('SCRIPT_ATTR_CSP_READINESS_FAILED: dist/index.html missing')

class AttributeInventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.event_attributes = []
        self.vue_event_directives = 0
        self.tags = 0

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        for name, _ in attrs:
            low = (name or '').lower()
            if low.startswith('on') and len(low) > 2:
                self.event_attributes.append((tag, low))
            if low.startswith('@') or low.startswith('v-on:'):
                self.vue_event_directives += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

parser = AttributeInventory()
parser.feed(INDEX.read_text(encoding='utf-8'))
parser.close()

if parser.event_attributes:
    sample = ', '.join(f'{tag}[{name}]' for tag, name in parser.event_attributes[:10])
    raise SystemExit(
        'SCRIPT_ATTR_CSP_READINESS_FAILED: real inline DOM event attributes remain; '
        'cannot enforce script-src-attr none: ' + sample
    )
if parser.vue_event_directives < 1:
    raise SystemExit(
        'SCRIPT_ATTR_CSP_READINESS_FAILED: no Vue event directives found; parser/readiness baseline may have drifted'
    )

print(
    'SCRIPT_ATTR_CSP_READINESS_OK: real-on*-attributes=0; '
    f'vue-event-directives={parser.vue_event_directives}; parsed-tags={parser.tags}; '
    'script-src-attr-none=safe-for-current-final-html'
)
