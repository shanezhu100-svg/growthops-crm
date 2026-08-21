from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'const resolveVisibleClientId=()=>{',
    "if(isAccountAssetPage()){",
    "const visibleClientId=resolveVisibleClientId();",
    "['selectedAssetClientId','assetClientId','clientAssetClientId']",
    "if(vm.currentPage==='client-detail'&&vm.selectedClientId",
    "visibleLabels.some(text=>text===name)",
    "bodyText.includes(name)",
):
    require(marker in security,f'account asset client context marker missing: {marker}')

asset_block=security.split("  const resolveCredentialClientId=()=>{",1)[1].split("    if(vm.currentPage==='client-detail'",1)[0]
require('resolveVisibleClientId()' in asset_block,'account asset resolver must use visible client identity')
require('selectedClientId' not in asset_block,'stale selectedClientId must not outrank the visible account-asset client')
require("crm_client_credential_status" in security,'credential presence status RPC must remain wired')
require("crm_reveal_client_secrets" in security,'secure Vault reveal RPC must remain wired')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';" in security,'standard eye icon must remain')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';" in security,'standard eye-slash icon must remain')
require("setTimeout(hide,10000)" in security,'10-second per-field hide must remain')
require("setTimeout(clearReveal,30000)" in security,'30-second Vault clear must remain')

print('ACCOUNT_ASSET_CLIENT_CONTEXT_OUTPUT_TESTS_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
