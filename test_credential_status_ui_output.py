from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')
status_sql=(root/'supabase/migrations/20260816_client_credential_status.sql').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "const STATUS_ATTR='data-growthops-credential-status'",
    "crm_client_credential_status",
    "applyCredentialStatusToCards",
    "ensureCredentialStatus",
    "credentialStatusFetchedAt",
    "row.accountCell.textContent='已录入'",
    "row.passwordCell.textContent='••••••••'",
    "['ADMIN','OPS'].includes",
    "now-credentialStatusFetchedAt<60000",
):
    require(marker in security,f'credential status UI marker missing: {marker}')

require("if(isAccountAssetPage())ensureCredentialStatus();" in security,'account asset page must refresh safe credential presence status')
require("row.accountCell.getAttribute(INLINE_ATTR)!=='1'" in security,'status metadata must not overwrite an active login-account reveal')
require("row.passwordCell.getAttribute(INLINE_ATTR)!=='1'" in security,'status metadata must not overwrite an active password reveal')
require("applyCredentialStatusToCards();\n  }\n\n  function make(" in security,'closing a reveal must restore safe recorded/masked status')

require("toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';" in security,'password control must use Font Awesome eye icon')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';" in security,'visible password control must use Font Awesome eye-slash icon')
require('👁' not in security and '🙈' not in security,'emoji password reveal icons must be removed')
require("setTimeout(hide,10000)" in security,'10-second per-field secret clear must remain')
require("setTimeout(clearReveal,30000)" in security,'30-second Vault clear must remain')

for marker in (
    'create or replace function public.crm_client_credential_status',
    "c.role not in ('ADMIN','OPS')",
    'crm_read_workspace_secrets',
    "'hasLoginAccount'",
    "'hasPassword'",
    "'has2FA'",
    "v_client->'fbLoginAccount'",
    "v_client->'fbLoginPassword'",
    "v_client->'tkLoginAccount'",
    "v_client->'tkLoginPassword'",
    'revoke all on function public.crm_client_credential_status(text,text) from public',
):
    require(marker in status_sql,f'credential status RPC marker missing: {marker}')

require("return coalesce(v_client" not in status_sql,'credential status RPC must never return the Vault client secret object')

print('CREDENTIAL_STATUS_UI_OUTPUT_TESTS_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest()+'; sql='+hashlib.sha256(status_sql.encode('utf-8')).hexdigest())
