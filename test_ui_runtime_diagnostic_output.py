from pathlib import Path

root=Path(__file__).resolve().parent
index=(root/'dist'/'index.html').read_text(encoding='utf-8')
diag=(root/'dist'/'ui-runtime-diagnostic.js').read_text(encoding='utf-8')

def require(cond,msg):
    if not cond: raise SystemExit(msg)

require(index.count('<script src="/ui-runtime-diagnostic.js"></script>')==1,'runtime diagnostic script tag missing/duplicated')
for marker in (
    'client-nav-diag-v1',
    'growthops-ui-runtime-diag',
    "window.addEventListener('pointerdown'",
    "window.addEventListener('click'",
    'document.elementsFromPoint',
    'CALL openClientDetail',
    'CALL navigateTo(',
    'VUE ERROR',
    'WINDOW ERROR',
    'PROMISE ERROR',
    'data-growthops-native-action',
    'pointer-events:none',
):
    require(marker in diag,f'runtime diagnostic marker missing: {marker}')
require('preventDefault()' not in diag,'diagnostic must not prevent user events')
require('stopImmediatePropagation()' not in diag,'diagnostic must not stop user events')
require('selectedClientId=' not in diag,'diagnostic must not print actual selected client id')
require('client.name' not in diag,'diagnostic must not print client names')
print('UI_RUNTIME_DIAGNOSTIC_OUTPUT_TESTS_OK')
