from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')
sql=(root/'supabase/migrations/20260816_credential_unlock_v4.sql').read_text(encoding='utf-8')

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
    "crm_reveal_client_secret_field_v4",
    'p_unlock_token:unlockToken',
    'credentialUnlockExpiresAt=Number.isFinite(expiresAt)?expiresAt:Date.now()+600000',
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
    "window.addEventListener('beforeunload',clearCredentialUnlock)",
    "window.addEventListener('pagehide',clearCredentialUnlock)",
):
    require(marker in security,f'credential unlock UI marker missing: {marker}')

# Final browser output must not call v3 directly; v3 is server-only after v4 migration.
require("cloud.rpc('crm_reveal_client_secret_field_v3'" not in security,
        'browser must not call v3 reveal RPC directly after v4 unlock')

unlock_start=security.find("  let credentialUnlockToken='';")
unlock_end=security.find('  const installProtectedFieldControl=',unlock_start)
require(unlock_start>=0 and unlock_end>unlock_start,'credential unlock helper block missing')
unlock_block=security[unlock_start:unlock_end]
require('localStorage.setItem' not in unlock_block and 'sessionStorage.setItem' not in unlock_block,
        'credential unlock token must remain memory-only')
require("localStorage.getItem(TOKEN_KEY)" in unlock_block,
        'unlock may read the existing CRM session token but must not persist the unlock token')

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
    'create or replace function public.crm_reveal_client_secret_field_v4',
    'u.unlock_hash=v_unlock_hash',
    'u.session_token_hash=v_session_hash',
    'u.user_id=c.user_id',
    'u.workspace_id=c.workspace_id',
    'u.expires_at > now()',
    "raise exception 'CREDENTIAL_UNLOCK_REQUIRED'",
    'return public.crm_reveal_client_secret_field_v3',
    'revoke execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from anon, authenticated, public',
):
    require(marker in sql,f'credential unlock SQL marker missing: {marker}')

# Password and unlock token are never part of audit detail objects.
for audit_action in ('CREDENTIAL_UNLOCK_FAILURE','CREDENTIAL_UNLOCK_THROTTLED','CREDENTIAL_UNLOCK'):
    require(audit_action in sql,f'audit action missing: {audit_action}')
require("jsonb_build_object('reason','INVALID_PASSWORD')" in sql,
        'invalid unlock audit must contain reason only')
require("jsonb_build_object('expiresInSeconds',600)" in sql,
        'successful unlock audit must contain expiry metadata only')

print('CREDENTIAL_UNLOCK_V4_OUTPUT_TESTS_OK: security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
