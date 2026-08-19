from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')
html=(root/'dist'/'index.html').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

# Removed top-level view-login feature must stay removed.
require('growthops-secure-credential-button' not in html,'top-level credential view button must remain removed')
require('查看登录资料</button>' not in html and '隐藏登录资料</button>' not in html,
        'top-level view/hide login material controls must remain removed')

# Refresh/loading behavior must cover both account-assets and client-detail.
loading_start=security.find("const applyCredentialLoadingToCards=()=>{")
loading_end=security.find("const applyCredentialStatusUnavailable=()=>{",loading_start)
require(loading_start>=0 and loading_end>loading_start,'credential loading helper missing')
loading_block=security[loading_start:loading_end]
require("if(!isCredentialSummaryContext())return;" in loading_block,
        'credential loading must cover account-assets and client-detail')
require("cell.textContent='读取中…';" in loading_block,'credential loading placeholder missing')

# A new client must clear stale state and enter loading before the safe-summary RPC.
ensure_start=security.find("const ensureAccountSafeSummary=()=>{")
ensure_end=security.find("const applyCredentialLoadingToCards=()=>{",ensure_start)
require(ensure_start>=0 and ensure_end>ensure_start,'safe-summary ensure helper missing')
ensure_block=security[ensure_start:ensure_end]
for marker in (
    'clearReveal();',
    'cell.removeAttribute(STATUS_ATTR);',
    'cell.removeAttribute(LOGIN_IDENTIFIER_ATTR);',
    'cell.removeAttribute(FIELD_REVEAL_ATTR);',
    'if(!accountSafeSummaryData)applyCredentialLoadingToCards();',
    "crm_client_account_safe_summary",
):
    require(marker in ensure_block,f'safe-summary refresh marker missing: {marker}')

# Once summary data lands, eye controls must be installed in the same render pass.
apply_start=security.find("const applyAccountSafeSummaryToCards=()=>{")
apply_end=security.find("const markAccountSafeSummaryUnavailable=()=>{",apply_start)
require(apply_start>=0 and apply_end>apply_start,'safe-summary apply helper missing')
apply_block=security[apply_start:apply_end]
require("row.accountCell.textContent=login||'未录入';" in apply_block,'real login identifier writer missing')
require("row.passwordCell.textContent=recorded?'••••••••':'未录入';" in apply_block,'masked password state writer missing')
require('installProtectedFieldControls();' in apply_block,'eye controls must install immediately after safe summary')

# Eye reveal must retain v4 admin unlock + single-field reveal and auto-hide.
for marker in (
    "toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';",
    'setTimeout(hide,10000)',
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    require(marker in security,f'protected credential eye marker missing: {marker}')

require("cloud.rpc('crm_reveal_client_secrets'" not in security,
        'legacy full-client reveal must remain absent from browser code')

print('CREDENTIAL_REFRESH_EYE_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest()+'; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
