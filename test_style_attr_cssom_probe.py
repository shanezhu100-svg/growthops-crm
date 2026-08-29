from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP = DIST / 'app'

if not INDEX.is_file():
    raise SystemExit('STYLE_ATTR_CSSOM_PROBE_FAILED: dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

bound = list(re.finditer(r'(?:\:style|v-bind\:style)\s*=\s*(["\'])(.*?)\1', html, flags=re.I | re.S))
if len(bound) != 1:
    raise SystemExit(f'STYLE_ATTR_CSSOM_PROBE_FAILED: expected one Vue bound style, found {len(bound)}')

print('STYLE_ATTR_CSSOM_PROBE_BOUND_STYLE: ' + re.sub(r'\s+', ' ', bound[0].group(2)).strip()[:500])

app_files = sorted(APP.glob('app-inline-*.js'))
if not app_files:
    raise SystemExit('STYLE_ATTR_CSSOM_PROBE_FAILED: externalized app JS missing')

hits = []
for path in app_files:
    text = path.read_text(encoding='utf-8')
    for match in re.finditer(r'\.style\s*(?:\.|\[)', text):
        start = max(0, match.start() - 180)
        end = min(len(text), match.end() + 220)
        snippet = re.sub(r'\s+', ' ', text[start:end]).strip()
        hits.append((path.name, match.start(), snippet))

if len(hits) != 8:
    raise SystemExit(f'STYLE_ATTR_CSSOM_PROBE_FAILED: expected eight .style sinks, found {len(hits)}')
for idx, (name, offset, snippet) in enumerate(hits, start=1):
    print(f'STYLE_ATTR_CSSOM_PROBE_CSSOM_{idx}: file={name}; offset={offset}; context={snippet}')

raise SystemExit('STYLE_ATTR_CSSOM_PROBE_COMPLETE: reviewed inventory emitted; no deployable artifact produced')
