from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
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
    "version:'5.1'",
    "prefetch:()=>credentialUiV51Prefetch()",
):
    require(marker in security,f'credential UI v5.1 prefetch marker missing: {marker}')

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
require("new Map()" in block or "credentialUiV51PrefetchCache" in security,'memory-only prefetch cache missing')
require("Date.now()-Number(cached.savedAt||0)>60000" in block,'prefetch cache TTL must remain 60 seconds')

for marker in (
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    "setTimeout(hide,10000)",
    "if(vm.currentUser?.role!=='ADMIN')",
):
    require(marker in security,f'v5 password safety marker missing after prefetch: {marker}')
for forbidden in (
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
):
    require(forbidden not in security,f'broader reveal call survived after prefetch: {forbidden}')

print('CREDENTIAL_UI_V51_PREFETCH_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
