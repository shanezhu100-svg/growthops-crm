from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')
unlock_sql=(root/'supabase/migrations/20260816_credential_unlock_v4.sql').read_text(encoding='utf-8')
v5_sql=(root/'supabase/migrations/20260821_credential_minimal_reveal_v5.sql').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "let credentialUnlockToken=''",
    "let credentialUnlockExpiresAt=0",
    "let credentialUnlockUserId=''",
    'clearCredentialUnlock',
    'hasCredentialUnlock',
    'requestCredentialUnlock',
    'ensureCredentialUnlock',
    '验证管理员身份',
    '验证并解锁',
    "type:'password'",
    "autocomplete:'off'",
    "let password=input.value;",
    "input.value='';",
    "password='';",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    'p_unlock_token:unlockToken',
    'p_field:field',
    "if(summary?.hasPassword)password=await revealValue('password')",
    "if(summary?.has2FA)twofa=await revealValue('twofa')",
    'credentialUnlockExpiresAt=Number.isFinite(expiresAt)?expiresAt:Date.now()+600000',
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
    "window.addEventListener('beforeunload',clearCredentialUnlock)",
    "window.addEventListener('pagehide',clearCredentialUnlock)",
):
    require(marker in security,f'credential unlock/minimal reveal UI marker missing: {marker}')

# Browser reveal call path may request only the v5 scalar transport. Legacy helper
# definitions still exist at this intermediate build stage and are stripped by v6,
# so scope this gate to active RPC/bundle-consumer markers rather than all strings.
for forbidden in (
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    'flattenSecretFields(bundle',
):
    require(forbidden not in security,f'broader credential reveal survived browser call path: {forbidden}')

unlock_start=security.find("  let credentialUnlockToken='';")
unlock_end=security.find('  const installProtectedFieldControl=',unlock_start)
require(unlock_start>=0 and unlock_end>unlock_start,'credential unlock helper block missing')
unlock_block=security[unlock_start:unlock_end]
require('localStorage.setItem' not in unlock_block and 'sessionStorage.setItem' not in unlock_block,
        'credential unlock token must remain memory-only')
require("localStorage.getItem(TOKEN_KEY)" in unlock_block,
        'pre-HttpOnly stage may read CRM session token but must never persist unlock token')

for marker in (
    'create table if not exists public.crm_credential_unlocks',
    'alter table public.crm_credential_unlocks enable row level security',
    'revoke all on table public.crm_credential_unlocks from public, anon, authenticated',
    "v_unlock_token := encode(extensions.gen_random_bytes(32),'hex')",
    'v_unlock_hash := public.crm_token_hash(v_unlock_token)',
    "v_expires_at := now() + interval '10 minutes'",
    "c.role <> 'ADMIN'",
    "v_user.password_hash <> extensions.crypt(coalesce(p_password,''),v_user.password_hash)",
    "l.action='CREDENTIAL_UNLOCK_FAILURE'",
    "v_recent_failures >= 5",
    "'CREDENTIAL_UNLOCK_FAILURE'",
    "'CREDENTIAL_UNLOCK_THROTTLED'",
):
    require(marker in unlock_sql,f'credential unlock SQL marker missing: {marker}')

for marker in (
    'create or replace function public.crm_reveal_client_secret_value_v5',
    "v_field not in ('password','twofa')",
    'u.unlock_hash = v_unlock_hash',
    'u.session_token_hash = v_session_hash',
    'u.user_id = c.user_id',
    'u.workspace_id = c.workspace_id',
    'u.expires_at > now()',
    "raise exception 'CREDENTIAL_UNLOCK_REQUIRED'",
    'v_bundle := public.crm_reveal_client_secret_field_v3',
    "v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','password')",
    "v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','twofa')",
    "return jsonb_build_object('value', v_value)",
    'revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from public, anon, authenticated',
    'revoke execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from public, anon, authenticated',
    'grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) to anon, service_role',
):
    require(marker in v5_sql,f'credential v5 SQL marker missing: {marker}')

# v5 browser-visible return must never construct a broader accountSecrets response.
return_tail=v5_sql[v5_sql.find('create or replace function public.crm_reveal_client_secret_value_v5'):]
require("return jsonb_build_object('value', v_value)" in return_tail,'v5 scalar return missing')
require("jsonb_build_object('accountSecrets'" not in return_tail,'v5 must not build accountSecrets response')

for audit_action in ('CREDENTIAL_UNLOCK_FAILURE','CREDENTIAL_UNLOCK_THROTTLED','CREDENTIAL_UNLOCK'):
    require(audit_action in unlock_sql,f'audit action missing: {audit_action}')
require("jsonb_build_object('reason','INVALID_PASSWORD')" in unlock_sql,
        'invalid unlock audit must contain reason only')
require("jsonb_build_object('expiresInSeconds',600)" in unlock_sql,
        'successful unlock audit must contain expiry metadata only')

print('CREDENTIAL_UNLOCK_V4_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
