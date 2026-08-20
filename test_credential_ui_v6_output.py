from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

# Atomic visual gate: keep layout, suppress transitional credential rows, then reveal
# the whole safe-summary pass together.
for marker in (
    "data-growthops-credential-v6-gate",
    "row.style.visibility='hidden'",
    "row.style.visibility='visible'",
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__={hide,reveal}",
):
    require(marker in html,f'credential UI v6 gate marker missing: {marker}')
require("if(cell.textContent)cell.textContent=''" not in html,
        'preboot must not churn credential text while the row is hidden')
require('读取中…' not in html,'loading placeholder must not survive into browser HTML')

for marker in (
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.hide?.();",
    "window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.reveal?.();",
    "version:'6.0'",
    "renderMode:'atomic-visibility'",
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
    "setTimeout(hide,10000)",
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    require(marker in security,f'credential UI v6 runtime marker missing: {marker}')

# Deprecated status/loading runtime must not ship. Earlier finalizers may still act as
# build-time canonical compatibility scaffolding, but the browser artifact is clean.
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
):
    require(forbidden not in security,f'deprecated credential runtime survived v6: {forbidden}')

# Prefetch stays memory-only and must never become a secret/password cache.
prefetch_start=security.find("  const credentialUiV51CandidateClientId=()=>{")
prefetch_end=security.find("  const ensureAccountSafeSummary=()=>{",prefetch_start)
require(prefetch_start>=0 and prefetch_end>prefetch_start,'v5.1 memory prefetch block missing after v6')
prefetch=security[prefetch_start:prefetch_end]
require("new Map()" in security,'memory-only safe-summary cache missing')
require("crm_client_account_safe_summary" in prefetch,'safe-summary prefetch RPC missing')
require("crm_reveal_client_secret_field_v4" not in prefetch,'prefetch must not read password / 2FA')
require("crm_reveal_client_secrets" not in prefetch,'prefetch must not read full secret tree')
require("localStorage.setItem" not in prefetch,'safe-summary prefetch must not persist to localStorage')
require("sessionStorage" not in prefetch,'safe-summary prefetch must not persist to sessionStorage')

# Final display source remains one safe-summary renderer.
require("row.accountCell.textContent=login||'未录入';" in security,'final login writer missing')
require("row.passwordCell.textContent='••••••••';" in security,'final masked-password writer missing')
require("row.passwordCell.textContent='未录入';" in security,'true-empty password writer missing')

print(
    'CREDENTIAL_UI_V6_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256((root/"dist"/"index.html").read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256((root/"dist"/"cloud-security-hotfix.js").read_bytes()).hexdigest()}'
)
