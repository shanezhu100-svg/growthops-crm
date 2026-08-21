from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
html = (dist / 'index.html').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')
p1_overrides = (dist / 'cloud-p1-overrides.js').read_text(encoding='utf-8')
security = (dist / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
stage = (root / 'supabase/migrations/20260815_security_vault_stage.sql').read_text(encoding='utf-8')
enforce = (root / 'supabase/migrations/20260815_security_vault_enforce.sql').read_text(encoding='utf-8')
hardening = (root / 'supabase/migrations/20260816_credential_reveal_hardening.sql').read_text(encoding='utf-8')

def require(condition, message):
    if not condition:
        raise SystemExit(message)

security_tag = '<script src="/cloud-security-hotfix.js"></script>'
require(html.count(security_tag) == 1, 'security hotfix script tag missing or duplicated')
require(
    '<script src="/cloud-p0-overrides.js"></script>' + security_tag in html,
    'security hotfix must load after P0 without disturbing P0/P1 order'
)

require(adapter.count("rpc('crm_login_v3'") == 1, 'v3 login endpoint missing or duplicated')
require(adapter.count("rpc('crm_load_state_v3'") == 1, 'v3 load endpoint missing or duplicated')
require("rpc('crm_login'" not in adapter, 'legacy crm_login endpoint remains in final adapter')
require("rpc('crm_load_state'" not in adapter, 'legacy crm_load_state endpoint remains in final adapter')
require("if(d?.error==='INVALID_CREDENTIALS'){vm.notify('账号或密码错误');return}" in adapter, 'P2 login guard lost')
require("finally{vm.loginForm.password=''}" in adapter, 'P2 login password cleanup lost')

require('let hydrating=false;' in adapter, 'cloud hydration guard missing')
require('let suppressPersist=false;' in adapter, 'nested persist suppression guard missing')
require('hydrating=true;' in adapter and 'finally{\n      hydrating=false;' in adapter, 'enter() does not bracket hydration')
require(
    'vm.persist=()=>{if(hydrating||suppressPersist)return true;' in adapter,
    'persist() is not suppressed during hydration/internal snapshot creation'
)
enter_block = adapter.split('async function enter(d){',1)[1].split('async function saveNow(){',1)[0]
require('vm.ensureDailyBackup()' not in enter_block, 'page load must not create/save a daily backup')
require('vm.persist()' not in enter_block, 'page load must not persist cloud state')
save_block = adapter.split('async function saveNow(){',1)[1].split('vm.persist=()=>',1)[0]
require(
    "suppressPersist=true;" in save_block and "if(vm.currentUser?.role==='ADMIN')vm.ensureDailyBackup()" in save_block,
    'ADMIN daily backup must be folded into an already-requested save'
)

require(
    p1_overrides.count("cloud.rpc('crm_load_state_v3',{p_token:token})") == 1,
    'P1 conflict recovery must use v3 redacted load endpoint exactly once'
)
require(
    "cloud.rpc('crm_load_state',{p_token:token})" not in p1_overrides,
    'P1 conflict recovery still calls legacy secret-bearing load endpoint'
)
require(
    '请先点击“导出本地脱敏副本”，导出成功后再重新载入云端最新版本' in p1_overrides,
    'P1 conflict recovery inline export guidance missing'
)
require(
    "sessionStorage.setItem('growthops_p1_conflict_backup_exported_at'" in p1_overrides,
    'P1 conflict recovery durable backup marker missing'
)
require(
    "sessionStorage.getItem('growthops_p1_conflict_backup_exported_at')" in p1_overrides,
    'P1 conflict recovery does not reuse durable backup marker'
)
require(
    "nextUrl.searchParams.set('_cloudReload',Date.now().toString())" in p1_overrides,
    'P1 conflict recovery cache-busting navigation marker missing'
)
require(
    'window.location.replace(nextUrl.toString())' in p1_overrides,
    'P1 conflict recovery must use hard navigation'
)
require(
    'window.location.reload()' not in p1_overrides,
    'P1 conflict recovery must not use reload() self-lock path'
)
require(
    "recoveryUrl.searchParams.has('_cloudReload')" in p1_overrides and
    "sessionStorage.removeItem('growthops_p1_conflict_backup_exported_at')" in p1_overrides,
    'P1 conflict recovery one-shot marker cleanup missing'
)

for key in (
    'fbloginpassword','tkloginpassword','twofactorsecret','recoverycodes','backupcodes','totpsecret'
):
    require(key in security, f'security redaction key missing: {key}')
require("vm.createBackupSnapshot=(notifyUser=false)=>" in security, 'redacted cloud snapshot override missing')
require("crm_reveal_client_secrets" in security, 'ADMIN on-demand reveal RPC missing')
require("setTimeout(clearReveal,30000)" in security, '30-second reveal auto-clear missing')
require("setTimeout(hide,10000)" in security, 'per-field 10-second secret reveal missing')
require("window.addEventListener('blur',clearReveal)" in security, 'credential reveal must clear on window blur')
require("window.addEventListener('pagehide',clearReveal)" in security, 'credential reveal must clear on page hide')
require('navigator.clipboard' not in security, 'security reveal must not copy secrets to clipboard automatically')
require('console.log' not in security and 'console.error' not in security, 'security hotfix must not log secret-bearing objects')

for marker in (
    'crm_workspace_secret_vault',
    'vault.create_secret',
    'vault.update_secret',
    'crm_extract_live_secrets',
    'crm_merge_secret_updates',
    'crm_login_v3',
    'crm_load_state_v3',
    'crm_reveal_client_secrets',
    "p_role in ('FINANCE','SALES','OPS')",
):
    require(marker in stage, f'stage migration marker missing: {marker}')

require("p_state ? 'clients'" in stage and "p_state ? 'mediaTools'" in stage, 'Vault extraction scope must be live clients/mediaTools only')
extract_live = stage.split('create or replace function public.crm_extract_live_secrets',1)[1].split('$$;',1)[0]
require("'backupSnapshots'" not in extract_live, 'backupSnapshots must not be copied into Vault live secret extraction')
require("set data=v_public_saved" in enforce, 'enforce migration must persist redacted public state only')
require("crm_redact_secrets(coalesce(data,'{}'::jsonb))" in enforce, 'enforce migration must purge residual workspace secrets')
require("declare s jsonb:=public.crm_redact_secrets" in enforce, 'enforce role view must redact ADMIN too')

for marker in (
    "v_session_created < now() - interval '12 hours'",
    "v_recent_5m >= 5",
    "v_recent_1h >= 20",
    "REVEAL_CLIENT_SECRETS_REAUTH_REQUIRED",
    "REVEAL_CLIENT_SECRETS_THROTTLED",
    "crm_server_audit_logs_reveal_user_created_idx",
    "revoke all on function public.crm_reveal_client_secrets(text,text) from public",
):
    require(marker in hardening,f'credential reveal hardening marker missing: {marker}')

print(
    'SECURITY_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()}; '
    f'adapter={hashlib.sha256((dist / "cloud-adapter.js").read_bytes()).hexdigest()}; '
    f'p1={hashlib.sha256((dist / "cloud-p1-overrides.js").read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256((dist / "cloud-security-hotfix.js").read_bytes()).hexdigest()}'
)
