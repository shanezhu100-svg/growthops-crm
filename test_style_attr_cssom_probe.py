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

bound_match = bound[0]
bound_context = re.sub(
    r'\s+', ' ', html[max(0, bound_match.start() - 450):min(len(html), bound_match.end() + 450)]
).strip()
print('STYLE_ATTR_CSSOM_PROBE_BOUND_STYLE: ' + re.sub(r'\s+', ' ', bound_match.group(2)).strip()[:500])
print('STYLE_ATTR_CSSOM_PROBE_BOUND_CONTEXT: ' + bound_context[:1200])

app_files = sorted(APP.glob('app-inline-*.js'))
if not app_files:
    raise SystemExit('STYLE_ATTR_CSSOM_PROBE_FAILED: externalized app JS missing')

hits = []
for path in app_files:
    text = path.read_text(encoding='utf-8')
    for match in re.finditer(r'\.style\s*(?:\.|\[)', text):
        start = max(0, match.start() - 260)
        end = min(len(text), match.end() + 320)
        snippet = re.sub(r'\s+', ' ', text[start:end]).strip()
        hits.append((path.name, match.start(), snippet))

if len(hits) != 8:
    raise SystemExit(f'STYLE_ATTR_CSSOM_PROBE_FAILED: expected eight .style sinks, found {len(hits)}')
for idx, (name, offset, snippet) in enumerate(hits, start=1):
    print(f'STYLE_ATTR_CSSOM_PROBE_CSSOM_{idx}: file={name}; offset={offset}; context={snippet}')

for path in app_files:
    text = path.read_text(encoding='utf-8')
    positions = [m.start() for m in re.finditer(r'roasBars', text)]
    for idx, pos in enumerate(positions[:6], start=1):
        snippet = re.sub(r'\s+', ' ', text[max(0, pos - 500):min(len(text), pos + 1100)]).strip()
        print(f'STYLE_ATTR_CSSOM_PROBE_ROAS_{path.name}_{idx}: {snippet}')

for css_path in sorted(APP.glob('app-style-*.css')):
    css = css_path.read_text(encoding='utf-8')
    for marker in ('growthops-credential-v6-gate', 'growthops-clipboard-fallback'):
        if marker in css:
            pos = css.index(marker)
            context = re.sub(r'\s+', ' ', css[max(0, pos - 300):min(len(css), pos + 650)]).strip()
            print(f'STYLE_ATTR_CSSOM_PROBE_CSS_{css_path.name}_{marker}: {context}')

raise SystemExit('STYLE_ATTR_CSSOM_PROBE_COMPLETE: reviewed inventory emitted; no deployable artifact produced')
