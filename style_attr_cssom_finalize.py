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
PENDING_OLD = "row.style.visibility='visible'; row.style.pointerEvents='none'; row.setAttribute('data-growthops-credential-v6-gate','pending');"
PENDING_NEW = "row.setAttribute('data-growthops-credential-v6-gate','pending');"
READY_OLD = "row.style.visibility='visible'; row.style.pointerEvents=''; row.setAttribute('data-growthops-credential-v6-gate','ready');"
READY_NEW = "row.setAttribute('data-growthops-credential-v6-gate','ready');"
COPY_OLD = "ta.style.position='fixed';ta.style.opacity='0';"
COPY_NEW = "ta.className='growthops-clipboard-fallback';"
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
if js2.count(PENDING_OLD) != 2:
    fail(f'credential pending style anchor drifted: {js2.count(PENDING_OLD)}')
if js2.count(READY_OLD) != 1:
    fail(f'credential ready style anchor drifted: {js2.count(READY_OLD)}')
if js3.count(COPY_OLD) != 1:
    fail(f'clipboard fallback style anchor drifted: {js3.count(COPY_OLD)}')
if CSS_LINK in html:
    fail('dynamic style link already present before finalization')
if html.count('</head>') != 1:
    fail('expected one </head> anchor')

html = html.replace(ROAS_OLD, ROAS_NEW, 1)
html = html.replace('</head>', CSS_LINK + '</head>', 1)
js2 = js2.replace(PENDING_OLD, PENDING_NEW)
js2 = js2.replace(READY_OLD, READY_NEW, 1)
js3 = js3.replace(COPY_OLD, COPY_NEW, 1)

INDEX.write_text(html, encoding='utf-8')
APP2.write_text(js2, encoding='utf-8')
APP3.write_text(js3, encoding='utf-8')
CSS.write_text(CSS_TEXT, encoding='utf-8')

print(
    'STYLE_ATTR_CSSOM_FINALIZE_OK: roas=progress-value; credential-gate=data-attribute-css; '
    'clipboard=class-css; v-show=0; output=/app/app-dynamic-style.css; '
    f'css-sha256={sha256(CSS_TEXT.encode("utf-8"))}; css-bytes={len(CSS_TEXT.encode("utf-8"))}'
)
