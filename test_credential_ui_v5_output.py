from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

require('id="growthops-credential-ui-v5-preboot"' in html,'credential UI v5 preboot missing')
require('data-growthops-credential-v5-state' in html,'credential UI v5 preboot state marker missing')
require('读取中…' not in html,'loading text must not survive into final HTML')
require('growthops-secure-credential-button' not in html,'removed top-level credential action must stay removed')

for marker in (
    "let credentialUiV5RequestSeq=0;",
    "let credentialUiV5State='idle';",
    "const credentialUiV5Render=()=>{",
    "const credentialUiV5Blank=clientId=>{",
    "const credentialUiV5DomReady=()=>{",
    "const credentialUiV5Error=()=>{",
    "const applyAccountSafeSummaryToCards=credentialUiV5Render;",
    "const markAccountSafeSummaryUnavailable=credentialUiV5Error;",
    "const applyCredentialLoadingToCards=()=>{};",
    "const applyCredentialStatusUnavailable=()=>{};",
    "const applyCredentialStatusToCards=()=>{};",
    "const ensureCredentialStatus=()=>{};",
    "const installProtectedFieldControls=()=>{};",
    "window.__GROWTHOPS_CREDENTIAL_UI_V5__={",
    "version:'5.0'",
):
    require(marker in security,f'credential UI v5 marker missing: {marker}')

require("row.accountCell.textContent=login||'未录入';" in security,'v5 login identifier final writer missing')
require("row.passwordCell.textContent='••••••••';" in security,'v5 masked password final writer missing')
require("row.passwordCell.textContent='未录入';" in security,'v5 true-empty password final writer missing')
require("row.accountCell.textContent='已录入'" not in security,'legacy boolean login status writer must be absent')
require("cell.textContent='读取中…'" not in security,'legacy loading text writer must be absent')

for marker in (
    'const requestId=++credentialUiV5RequestSeq;',
    'requestId!==credentialUiV5RequestSeq||resolveCredentialClientId()!==clientId',
    "credentialUiV5State==='error'",
    'now-credentialUiV5LastErrorAt<10000',
):
    require(marker in security,f'credential UI v5 request-state marker missing: {marker}')

# Password eye remains protected by ADMIN unlock, but its network transport is now v5
# scalar-only. v3/v4 bundle calls and browser-side bundle flattening are forbidden.
for marker in (
    'installProtectedFieldControl(row,summary);',
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';",
    'setTimeout(hide,10000)',
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    require(marker in security,f'credential v5 eye marker missing after v5 renderer: {marker}')
for forbidden in (
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    'flattenSecretFields(bundle',
):
    require(forbidden not in security,f'broader reveal path survived v5 renderer: {forbidden}')

require('ensureCredentialStatus();ensureAccountSafeSummary()' not in security,
        'periodic scan must not run the legacy credential status path')
require('ensureAccountSafeSummary();installProtectedFieldControls();' not in security,
        'periodic scan must not run the legacy plural eye installer')

print(
    'CREDENTIAL_UI_V5_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; '
    f'index={hashlib.sha256((root/"dist"/"index.html").read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256((root/"dist"/"cloud-security-hotfix.js").read_bytes()).hexdigest()}'
)
