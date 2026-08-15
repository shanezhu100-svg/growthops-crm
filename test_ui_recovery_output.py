from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
html = (dist / 'index.html').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')
ui = (dist / 'cloud-ui-recovery.js').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


security_tag = '<script src="/cloud-security-hotfix.js"></script>'
ui_tag = '<script src="/cloud-ui-recovery.js"></script>'
require(html.count(ui_tag) == 1, 'UI recovery script tag missing or duplicated')
require(security_tag + ui_tag in html, 'UI recovery must load after the security hotfix')

require('let lastSavedStateJson=null;' in adapter, 'last confirmed cloud state marker missing')
require('lastSavedStateJson=JSON.stringify(payload());' in adapter, 'hydrated cloud baseline missing')
require('if(stateJson===lastSavedStateJson)return true;' in adapter, 'unchanged save de-duplication missing')
require('lastSavedStateJson=stateJson;return true;' in adapter, 'confirmed save baseline update missing')
require('if(hydrating||suppressPersist)return true;' in adapter, 'existing hydration guard must remain intact')
require("rpc('crm_login_v3'" in adapter and "rpc('crm_load_state_v3'" in adapter, 'security v3 endpoints must remain intact')

for marker in (
    'growthops-session-restore-mask',
    'post-interaction-force-render',
    'sanitized-runtime-error-code',
    "document.addEventListener('click',queueRenderRecovery,false)",
    "document.addEventListener('submit',queueRenderRecovery,false)",
    "reportRuntime('UI-VUE-01')",
    "reportRuntime('UI-ASYNC-01')",
):
    require(marker in ui, f'UI recovery marker missing: {marker}')

require('error?.message' not in ui and 'error.message' not in ui, 'UI recovery must not display raw error messages')
require('localStorage.getItem(TOKEN_KEY)' in ui, 'session restore mask must be token-aware')
require('vm.$forceUpdate' in ui, 'post-interaction Vue render recovery missing')

print(
    'UI_RECOVERY_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()}; '
    f'adapter={hashlib.sha256((dist / "cloud-adapter.js").read_bytes()).hexdigest()}; '
    f'ui={hashlib.sha256((dist / "cloud-ui-recovery.js").read_bytes()).hexdigest()}'
)
