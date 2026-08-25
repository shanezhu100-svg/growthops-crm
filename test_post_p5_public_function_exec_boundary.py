from pathlib import Path
import re

root = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def statements(path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'--[^\n]*', '', text)
    return [re.sub(r'\s+', ' ', item).strip().lower() for item in text.split(';') if item.strip()]


migration_path = root / 'supabase' / 'migrations' / '20260824_post_p5_revoke_rls_auto_enable_service_role_exec.sql'
rollback_path = root / 'supabase' / 'rollback' / '20260824_post_p5_restore_rls_auto_enable_service_role_exec.sql'
preflight_path = root / 'supabase' / 'baseline' / 'post_p5_public_function_exec_boundary_preflight.sql'
postcheck_path = root / 'supabase' / 'baseline' / 'post_p5_public_function_exec_boundary_check.sql'

migration = statements(migration_path)
rollback = statements(rollback_path)
require(migration == ['revoke execute on function public.rls_auto_enable() from service_role'], 'migration must contain the single exact service_role revoke')
require(rollback == ['grant execute on function public.rls_auto_enable() to service_role'], 'rollback must contain the single exact service_role grant')

expected_names = {
    'crm_bootstrap_admin',
    'crm_client_account_safe_summary',
    'crm_delete_user',
    'crm_list_users',
    'crm_load_state_v3',
    'crm_login_v3',
    'crm_logout',
    'crm_public_status',
    'crm_reveal_client_secret_value_v5',
    'crm_save_state',
    'crm_unlock_credentials_v1',
    'crm_upsert_user',
}
require(len(expected_names) == 12, 'service-role target allowlist must remain exactly 12 CRM entry functions')

for sql_path in (preflight_path, postcheck_path):
    raw = sql_path.read_text(encoding='utf-8')
    body = re.sub(r'--[^\n]*', '', raw)
    require(not re.search(r'(?im)^\s*(grant|revoke|create|alter|drop|insert|update|delete|truncate)\b', body), f'{sql_path.name} must remain read-only')
    for marker in (
        "n.nspname = 'public'",
        "has_function_privilege('anon'",
        "has_function_privilege('authenticated'",
        "has_function_privilege('service_role'",
        "p.proname = 'rls_auto_enable'",
        "pg_get_function_result(p.oid) = 'event_trigger'",
        "e.evtname = 'ensure_rls'",
        'event_bound_to_target',
    ):
        require(marker in raw, f'{sql_path.name} missing boundary marker: {marker}')

preflight = preflight_path.read_text(encoding='utf-8')
require('service_role_exec' in preflight, 'preflight lost effective service-role count')
require('target_service_role_execute' in preflight, 'preflight lost target service-role truth')

postcheck = postcheck_path.read_text(encoding='utf-8')
for name in expected_names:
    require(name in postcheck, f'post-check allowlist missing {name}')
require('unexpected_service_role_exec' in postcheck, 'post-check must fail visibly on unexpected public service-role functions')
require('missing_expected_service_role_exec' in postcheck, 'post-check must detect missing expected service-role entries')
require('target_postgres_execute' in postcheck, 'post-check must preserve postgres EXECUTE')
require('target_service_role_execute' in postcheck, 'post-check must verify service_role removal')
require("e.evtenabled::text as enabled" in postcheck, 'post-check must preserve event enabled-state visibility')
require('e.evttags' in postcheck, 'post-check must preserve event tag visibility')

old_gate = (root / 'test_post_p5_service_role_rpc_minimization.py').read_text(encoding='utf-8')
for name in expected_names:
    require(name in old_gate, f'existing CRM service-role gate no longer preserves {name}')
require("service-role=12" in old_gate, 'existing CRM gate target count drifted')

current_state = (root / 'docs' / 'cloudflare-migration' / 'CURRENT_STATE.md').read_text(encoding='utf-8')
for marker in (
    'all `public` functions',
    '`anon / authenticated / service_role`: `0 / 0 / 12`',
    '`rls_auto_enable()`',
    '`ensure_rls`',
    'postgres-only for direct EXECUTE',
):
    require(marker in current_state, f'CURRENT_STATE missing accepted all-public boundary marker: {marker}')

# The exact migration that established this boundary remains historical ledger
# evidence even after later accepted migrations become the current Production head.
ledger = (root / 'docs' / 'cloudflare-migration' / 'P0_MIGRATION_LEDGER.md').read_text(encoding='utf-8')
require('`20260825032049` | `post_p5_revoke_rls_auto_enable_service_role_exec` | `supabase/migrations/20260824_post_p5_revoke_rls_auto_enable_service_role_exec.sql`' in ledger, 'migration ledger missing applied all-public boundary migration mapping')

build = (root / 'build.sh').read_text(encoding='utf-8')
require(build.count('python3 test_post_p5_public_function_exec_boundary.py') == 1, 'build must execute all-public function boundary gate exactly once')

print(
    'POST_P5_PUBLIC_FUNCTION_EXEC_BOUNDARY_PACKAGE_OK: '
    'anon=0; authenticated=0; service-role-target=12; '
    'rls-auto-enable=postgres-only; ensure-rls=preserved; production-change=applied+verified'
)
