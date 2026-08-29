from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP_DIR = DIST / 'app'

EXPECTED = {
    'app-style-01.css': ('33a4a117d6b9e820b389e09d87a4ccb94242fb043e80ea087f72c17f46861a70', 13916),
    'app-style-02.css': ('01ed16d03067a8879b877440574fbc6d98af53e0909685e1a23271169c149997', 418),
    'app-style-03.css': ('64bd5db676657f40c7962080ce62f3b74125865c3f084a67ce21d0fc77ed00b6', 401),
    'app-style-04.css': ('59de39d8388f561c5229cfa39f7d4c5299b34997c21e3c142d9ced067850a11e', 201),
}
REVIEWED_IDS = {
    'growthops-session-restore-style',
    'growthops-credential-v6-placeholder-style',
    'growthops-module-home-navigation-style',
}


def fail(message: str) -> None:
    raise SystemExit('INLINE_STYLE_STATIC_OUTPUT_FAILED: ' + message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
if re.search(r'<style\b', html, flags=re.I):
    fail('inline <style> element remains')

class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.links = []
        self.literal_style_attrs = 0
        self.bound_style_attrs = 0

    def handle_starttag(self, tag, attrs):
        attr_map = {str(k).lower(): v for k, v in attrs if k}
        if tag.lower() == 'link' and (attr_map.get('rel') or '').lower() == 'stylesheet':
            self.links.append((attr_map.get('href'), attr_map.get('id')))
        for name, _ in attrs:
            low = (name or '').lower()
            if low == 'style':
                self.literal_style_attrs += 1
            elif low in (':style', 'v-bind:style'):
                self.bound_style_attrs += 1

parser = Inventory()
parser.feed(html)
parser.close()

for index, (name, (expected_sha, expected_size)) in enumerate(EXPECTED.items(), start=1):
    path = APP_DIR / name
    if not path.is_file():
        fail('missing dist/app/' + name)
    data = path.read_bytes()
    if len(data) != expected_size:
        fail(f'{name} size drift: expected={expected_size}; actual={len(data)}')
    actual_sha = sha256(path)
    if actual_sha != expected_sha:
        fail(f'{name} hash drift: expected={expected_sha}; actual={actual_sha}')
    href = '/app/' + name
    if sum(1 for found_href, _ in parser.links if found_href == href) != 1:
        fail(f'{href} stylesheet link must occur exactly once')

for style_id in REVIEWED_IDS:
    matches = [(href, found_id) for href, found_id in parser.links if found_id == style_id]
    if len(matches) != 1:
        fail(f'reviewed style marker id must be preserved on exactly one link: {style_id}')
    if not (matches[0][0] or '').startswith('/app/app-style-'):
        fail(f'reviewed style marker id moved to unexpected resource: {style_id}')

if parser.literal_style_attrs != 0:
    fail(f'literal style attributes appeared unexpectedly: {parser.literal_style_attrs}')
if parser.bound_style_attrs != 1:
    fail(f'reviewed Vue bound style inventory drifted: {parser.bound_style_attrs}')

print(
    'INLINE_STYLE_STATIC_OUTPUT_OK: styles=4; inline-style-elements=0; '
    'literal-style-attrs=0; vue-bound-style=1; reviewed-ids=3; '
    + '; '.join(f'{name}={digest}/{size}B' for name, (digest, size) in EXPECTED.items())
)
