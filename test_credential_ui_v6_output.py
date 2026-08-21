from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "growthops-credential-v6-placeholder-style",
    "data-growthops-credential-v6-gate",
    "data-growthops-credential-v6-placeholder-kind",
    "const alreadyPlaceholder=",
    "if(!alreadyPlaceholder){",
    "row.style.visibility='visible'",
    "const clearPlaceholder=()=>{",
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__={hide,reveal}",
):
    require(marker in html,f'credential UI v6 placeholder marker missing: {marker}')
require("row.style.visibility='hidden'" not in html,
        'credential rows must not be hidden while safe summary loads')
require("if(cell.textContent)cell.textContent=''" not in html,
        'preboot must not expose or churn stale credential fallback text')
require('读取中…' not in html,'legacy textual loading placeholder must not survive into browser HTML')

for marker in (
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.hide?.();",
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.reveal?.();",
    "version:'6.3'",
    "renderMode:'atomic-placeholder-idempotent'",
    "runtimeCleanup:true",
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    "const locateCredentialRows=()=>{",
    "const prepareInlineCell=(cell,kind)=>{",
    "setTimeout(hide,10000)",
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    require(marker in security,f'credential UI v6 runtime marker missing: {marker}')

for forbidden in (
    "crm_client_credential_status",
    "growthops_credential_status_v2",
    "credentialStatusCacheKey",
    "readCredentialStatusCache",
    "writeCredentialStatusCache",
    "row.accountCell.textContent='已录入'",
    "cell.textContent='读取中…'",
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "flattenSecretFields(bundle",
    "setInterval(ensureRevealButton,300)",
    "function ensureRevealButton()",
    "async function revealSelectedClient()",
    "accountAssetRevealButtons",
    "secureRevealButtons",
    "setRevealButtonState",
    "setInlineValue=(cell,value,kind)",
    "setInlineSecretControl=(cell,value)",
    "applyInlineSecrets(secretTree)",
    "renderRevealModal(clientId,secretTree)",
    "const ensureCredentialStatus=()=>{}",
    "const applyCredentialStatusToCards=()=>{}",
    "const applyCredentialLoadingToCards=()=>{}",
    "const installProtectedFieldControls=()=>{}",
    "growthops-secure-credential-button",
):
    require(forbidden not in security,f'deprecated credential runtime survived v6 cleanup: {forbidden}')

prefetch_start=security.find("  const credentialUiV51CandidateClientId=()=>{")
prefetch_end=security.find("  const ensureAccountSafeSummary=()=>{",prefetch_start)
require(prefetch_start>=0 and prefetch_end>prefetch_start,'v5.1 memory prefetch block missing after v6')
prefetch=security[prefetch_start:prefetch_end]
require("new Map()" in security,'memory-only safe-summary cache missing')
require("crm_client_account_safe_summary" in prefetch,'safe-summary prefetch RPC missing')
for forbidden in (
    "crm_reveal_client_secret_value_v5",
    "crm_reveal_client_secret_field_v4",
    "crm_reveal_client_secret_field_v3",
    "crm_reveal_client_secrets",
):
    require(forbidden not in prefetch,f'prefetch must not read password / 2FA: {forbidden}')
require("localStorage.setItem" not in prefetch,'safe-summary prefetch must not persist to localStorage')
require("sessionStorage" not in prefetch,'safe-summary prefetch must not persist to sessionStorage')

require("row.accountCell.textContent=login||'未录入';" in security,'final login writer missing')
require("row.passwordCell.textContent='••••••••';" in security,'final masked-password writer missing')
require("row.passwordCell.textContent='未录入';" in security,'true-empty password writer missing')

print(
    'CREDENTIAL_UI_V6_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; '
    f'index={hashlib.sha256((root/"dist"/"index.html").read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256((root/"dist"/"cloud-security-hotfix.js").read_bytes()).hexdigest()}'
)
