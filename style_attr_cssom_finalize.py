from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP = DIST / 'app'
APP2 = APP / 'app-inline-02.js'
APP3 = APP / 'app-inline-03.js'
CSS = APP / 'app-dynamic-style.css'

ROAS_OLD = '<div class="h-3 rounded-full bg-slate-100 overflow-hidden"><div class="h-full rounded-full" :class="bar.className" :style="{width:bar.width+\'%\'}"></div></div>'
ROAS_NEW = '<progress class="growthops-roas-progress" :class="bar.className" :value="bar.width" max="100"></progress>'
ROW_VISIBILITY = "row.style.visibility='visible';"
ROW_PENDING_POINTER = "row.style.pointerEvents='none';"
ROW_READY_POINTER = "row.style.pointerEvents='';"
COPY_POSITION = "ta.style.position='fixed';"
COPY_OPACITY = "ta.style.opacity='0';"
COPY_CLASS = "ta.className='growthops-clipboard-fallback';"
CSS_LINK = '<link rel="stylesheet" href="/app/app-dynamic-style.css" />'

CSS_TEXT = '''/* CSP-safe replacements for the final dynamic style sinks. */
[data-growthops-credential-v6-gate="pending"],
[data-growthops-credential-v6-gate="ready"] {
  visibility: visible;
}
[data-growthops-credential-v6-gate="pending"] {
  pointer-events: none;
}
[data-growthops-credential-v6-gate="ready"] {
  pointer-events: auto;
}
.growthops-clipboard-fallback {
  position: fixed;
  opacity: 0;
}
.growthops-roas-progress {
  display: block;
  width: 100%;
  height: 0.75rem;
  border: 0;
  border-radius: 9999px;
  overflow: hidden;
  -webkit-appearance: none;
  appearance: none;
  background: #f1f5f9;
}
.growthops-roas-progress::-webkit-progress-bar {
  background: #f1f5f9;
  border-radius: 9999px;
}
.growthops-roas-progress::-webkit-progress-value {
  border-radius: 9999px;
}
.growthops-roas-progress::-moz-progress-bar {
  border-radius: 9999px;
}
.growthops-roas-progress.bg-blue-600::-webkit-progress-value {
  background: #2563eb;
}
.growthops-roas-progress.bg-blue-600::-moz-progress-bar {
  background: #2563eb;
}
.growthops-roas-progress.bg-slate-950::-webkit-progress-value {
  background: #020617;
}
.growthops-roas-progress.bg-slate-950::-moz-progress-bar {
  background: #020617;
}
'''


def fail(message: str) -> None:
    raise SystemExit('STYLE_ATTR_CSSOM_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


for path in (INDEX, APP2, APP3):
    if not path.is_file():
        fail(f'missing {path.relative_to(ROOT)}')

html = INDEX.read_text(encoding='utf-8')
js2 = APP2.read_text(encoding='utf-8')
js3 = APP3.read_text(encoding='utf-8')

if html.count(ROAS_OLD) != 1:
    fail(f'ROAS bound-style anchor drifted: {html.count(ROAS_OLD)}')
# Probe-established inventory: credential preboot has exactly three visibility
# writes, two pending pointer-event writes, and one ready pointer-event write.
# Count the atomic sinks independently so harmless whitespace/layout changes do
# not make the migration brittle, while any semantic inventory drift still fails.
expected_js2 = (
    (ROW_VISIBILITY, 3, 'credential visibility'),
    (ROW_PENDING_POINTER, 2, 'credential pending pointerEvents'),
    (ROW_READY_POINTER, 1, 'credential ready pointerEvents'),
)
for anchor, expected, label in expected_js2:
    actual = js2.count(anchor)
    if actual != expected:
        fail(f'{label} anchor drifted: expected={expected}; actual={actual}')
if js3.count(COPY_POSITION) != 1:
    fail(f'clipboard position style anchor drifted: {js3.count(COPY_POSITION)}')
if js3.count(COPY_OPACITY) != 1:
    fail(f'clipboard opacity style anchor drifted: {js3.count(COPY_OPACITY)}')
if COPY_CLASS in js3:
    fail('clipboard fallback class already present before finalization')
if CSS_LINK in html:
    fail('dynamic style link already present before finalization')
if html.count('</head>') != 1:
    fail('expected one </head> anchor')

html = html.replace(ROAS_OLD, ROAS_NEW, 1)
html = html.replace('</head>', CSS_LINK + '</head>', 1)
js2 = js2.replace(ROW_VISIBILITY, '')
js2 = js2.replace(ROW_PENDING_POINTER, '')
js2 = js2.replace(ROW_READY_POINTER, '')
js3 = js3.replace(COPY_POSITION, COPY_CLASS, 1)
js3 = js3.replace(COPY_OPACITY, '', 1)

# Fail before writing if any reviewed first-party style sink survived the exact
# inventory migration. The permanent output gate performs a broader regex scan.
for anchor, _, label in expected_js2:
    if anchor in js2:
        fail(f'{label} sink remains after replacement')
for anchor, label in ((COPY_POSITION, 'clipboard position'), (COPY_OPACITY, 'clipboard opacity')):
    if anchor in js3:
        fail(f'{label} sink remains after replacement')

INDEX.write_text(html, encoding='utf-8')
APP2.write_text(js2, encoding='utf-8')
APP3.write_text(js3, encoding='utf-8')
CSS.write_text(CSS_TEXT, encoding='utf-8')

print(
    'STYLE_ATTR_CSSOM_FINALIZE_OK: roas=progress-value; credential-gate=data-attribute-css; '
    'credential-sinks=3-visibility+2-pending-pointer+1-ready-pointer; '
    'clipboard=class-css; v-show=0; output=/app/app-dynamic-style.css; '
    f'css-sha256={sha256(CSS_TEXT.encode("utf-8"))}; css-bytes={len(CSS_TEXT.encode("utf-8"))}'
)
