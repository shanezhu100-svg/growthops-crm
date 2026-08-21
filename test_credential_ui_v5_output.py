from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

require('id="growthops-credential-ui-v5-preboot"' in html,'credential UI preboot missing')
require('data-growthops-credential-v5-state' in html,'credential UI preboot state marker missing')
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
    "version:'5.1'",
    "const credentialUiV51PrefetchCache=new Map();",
    "const credentialUiV51CandidateClientId=()=>{",
    "const credentialUiV51Cached=clientId=>{",
    "const credentialUiV51Remember=(clientId,data)=>{",
    "const credentialUiV51Prefetch=()=>{",
    "const credentialUiV51ClearPrefetch=()=>{",
    "credentialUiV51Prefetch();",
    "const prefetched=credentialUiV51Cached(clientId);",
    "credentialUiV51Remember(clientId,accountSafeSummaryData);",
    "if(document.hidden)credentialUiV51ClearPrefetch();",
    "window.addEventListener('beforeunload',credentialUiV51ClearPrefetch);",
    "window.addEventListener('pagehide',credentialUiV51ClearPrefetch);",
    "prefetch:()=>credentialUiV51Prefetch()",
):
    require(marker in security,f'credential controller marker missing: {marker}')

require("row.accountCell.textContent=login||'未录入';" in security,'login identifier final writer missing')
require("row.passwordCell.textContent='••••••••';" in security,'masked password final writer missing')
require("row.passwordCell.textContent='未录入';" in security,'true-empty password final writer missing')
require("row.accountCell.textContent='已录入'" not in security,'legacy boolean login status writer must be absent')
require("cell.textContent='读取中…'" not in security,'legacy loading text writer must be absent')

for marker in (
    'const requestId=++credentialUiV5RequestSeq;',
    'requestId!==credentialUiV5RequestSeq||resolveCredentialClientId()!==clientId',
    "credentialUiV5State==='error'",
    'now-credentialUiV5LastErrorAt<10000',
    'installProtectedFieldControl(row,summary);',
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';",
    'setTimeout(hide,10000)',
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    require(marker in security,f'credential controller safety marker missing: {marker}')

for forbidden in (
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    'flattenSecretFields(bundle',
):
    require(forbidden not in security,f'broader reveal path survived credential controller: {forbidden}')

require('ensureCredentialStatus();ensureAccountSafeSummary()' not in security,
        'periodic scan must not run the legacy credential status path')
require('ensureAccountSafeSummary();installProtectedFieldControls();' not in security,
        'periodic scan must not run the legacy plural eye installer')

start=security.find("  const credentialUiV51CandidateClientId=()=>{")
end=security.find("  const ensureAccountSafeSummary=()=>{",start)
require(start>=0 and end>start,'unable to bound v5.1 prefetch helper block')
block=security[start:end]
require("crm_client_account_safe_summary" in block,'safe-summary prefetch RPC missing')
for forbidden in (
    "crm_reveal_client_secret_value_v5",
    "crm_reveal_client_secret_field_v4",
    "crm_reveal_client_secret_field_v3",
    "crm_reveal_client_secrets",
):
    require(forbidden not in block,f'prefetch must never read password / 2FA: {forbidden}')
require("localStorage.setItem" not in block,'prefetch must not persist safe summary to localStorage')
require("sessionStorage" not in block,'prefetch must not persist safe summary to sessionStorage')
require("Date.now()-Number(cached.savedAt||0)>60000" in block,'prefetch cache TTL must remain 60 seconds')

index_hash=hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest()
security_hash=hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest()
require(index_hash=='3fb5874a43264d74e55222be7c19fa2a0abaa516a0b3fe480e6bcf327cdbe11e',
        'credential controller index drifted from production v5.1 baseline: '+index_hash)
require(security_hash=='c47e0ebc7c5c09fdee1f542974ec4e560e5d46987f523d1995f2a4d34d51976c',
        'credential controller security drifted from production v5.1 baseline: '+security_hash)
print('CREDENTIAL_UI_CONTROLLER_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; index='+index_hash+'; security='+security_hash)
