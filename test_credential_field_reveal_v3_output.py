from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')
sql=(root/'supabase/migrations/20260816_credential_field_reveal_v3.sql').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "const FIELD_REVEAL_ATTR='data-growthops-field-reveal'",
    'installProtectedFieldControl',
    'installProtectedFieldControls',
    'crm_reveal_client_secret_field_v3',
    'p_platform:String(row.platform||\'\')',
    'p_account_id:accountIdForProtectedField(row)||null',
    "toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';",
    "toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';",
    'fieldTimer=setTimeout(hide,10000)',
    "visibleValue=''",
    'bundle=null;',
    'fields.length=0;',
    'revealSelectedClientLegacy',
    'if(isAccountAssetPage())',
    '登录账号 / 邮箱已显示；密码 / 2FA 请点击对应眼睛短暂查看',
):
    require(marker in security,f'per-field reveal UI marker missing: {marker}')

require("return revealSelectedClientLegacy();" in security,'client-detail compatibility fallback missing')
require("if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();installProtectedFieldControls();}" in security,
        'account asset page must install protected field controls after safe summary')
require("el.removeAttribute(FIELD_REVEAL_ATTR);" in security,'field reveal marker must clear with reveal state')

# The account-asset path must not call the old full-client RPC before the per-field
# control is used. The old RPC is retained only inside the client-detail fallback.
wrapper_start=security.find('  async function revealSelectedClient(){')
wrapper_end=security.find('  function ensureRevealButton(){',wrapper_start)
require(wrapper_start>=0 and wrapper_end>wrapper_start,'reveal wrapper missing')
wrapper=security[wrapper_start:wrapper_end]
require('crm_reveal_client_secrets' not in wrapper,'account asset reveal wrapper must not fetch full client secret tree')

for marker in (
    'create or replace function public.crm_reveal_client_secret_field_v3',
    "c.role <> 'ADMIN'",
    "v_platform not in ('facebook','tiktok','google','instagram')",
    "v_session_created < now() - interval '12 hours'",
    "l.action = 'REVEAL_CLIENT_SECRET_FIELD'",
    "v_recent_5m >= 10 or v_recent_1h >= 40",
    "'REVEAL_CLIENT_SECRET_FIELD'",
    "'rateLimitVersion',v_limit_version",
    "public.crm_strip_login_identifier_secrets",
    "v_client->'fbLoginPassword'",
    "v_client->'tkLoginPassword'",
    "v_client->'googleAccounts'",
    "v_client->'instagramAccounts'",
    'revoke all on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from public',
):
    require(marker in sql,f'per-field reveal SQL marker missing: {marker}')

require("'loginAccount'," not in sql and "'fbLoginAccount'," not in sql and "'tkLoginAccount'," not in sql,
        'per-field reveal response must not intentionally return login identifiers')
require("jsonb_build_object('clientId'" not in sql,
        'audit and response construction should remain explicit and secret-free')

print('CREDENTIAL_FIELD_REVEAL_V3_OUTPUT_TESTS_OK: security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
