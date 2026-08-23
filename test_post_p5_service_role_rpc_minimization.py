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


revoke_signatures = [
    'crm_cap_session_expiry_v2()',
    'crm_client_credential_status(text,text)',
    'crm_extract_live_secrets(jsonb)',
    'crm_extract_secrets(jsonb)',
    'crm_is_secret_key(text)',
    'crm_limit_active_sessions_per_user()',
    'crm_load_state(text)',
    'crm_login(text,text)',
    'crm_merge_secret_updates(jsonb,jsonb)',
    'crm_prune_live_secrets(jsonb,jsonb)',
    'crm_read_workspace_secrets(uuid)',
    'crm_redact_secrets(jsonb)',
    'crm_restore_role_restricted(text,jsonb,jsonb)',
    'crm_restore_secrets(jsonb,jsonb)',
    'crm_reveal_client_secret_field_v3(text,text,text,text)',
    'crm_reveal_client_secret_field_v4(text,text,text,text,text)',
    'crm_reveal_client_secrets(text,text)',
    'crm_revoke_unlocks_on_membership_security_change()',
    'crm_revoke_unlocks_on_user_security_change()',
    'crm_role_view_state(text,jsonb)',
    'crm_secret_tree_nonempty(jsonb)',
    'crm_secret_value_nonempty(jsonb)',
    'crm_secret_value_text_v5(jsonb,text)',
    'crm_session_context(text)',
    'crm_strip_login_identifier_secrets(jsonb)',
    'crm_token_hash(text)',
    'crm_workspace_state_secret_guard()',
    'crm_write_workspace_secrets(uuid,jsonb,uuid)',
]

preserved_names = {
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

bff_names = preserved_names - {'crm_bootstrap_admin'}

migration_path = root / 'supabase' / 'migrations' / '20260823_revoke_internal_service_role_exec.sql'
rollback_path = root / 'supabase' / 'rollback' / '20260823_restore_internal_service_role_exec.sql'
preflight_path = root / 'supabase' / 'baseline' / 'post_p5_service_role_rpc_preflight.sql'
postcheck_path = root / 'supabase' / 'baseline' / 'post_p5_service_role_rpc_minimize_check.sql'
doc_path = root / 'docs' / 'cloudflare-migration' / 'POST_P5_SERVICE_ROLE_RPC_MINIMIZATION.md'

migration = statements(migration_path)
rollback = statements(rollback_path)
expected_migration = [f'revoke execute on function public.{sig} from service_role' for sig in revoke_signatures]
expected_rollback = [f'grant execute on function public.{sig} to service_role' for sig in revoke_signatures]

require(len(revoke_signatures) == 28 and len(set(revoke_signatures)) == 28, 'expected revoke inventory must contain 28 unique signatures')
require(migration == expected_migration, f'service_role migration scope drift: {migration!r}')
require(rollback == expected_rollback, f'service_role rollback scope drift: {rollback!r}')
require(all(' from service_role' in stmt for stmt in migration), 'migration must revoke only from service_role')
require(all(' to service_role' in stmt for stmt in rollback), 'rollback must grant only to service_role')
for forbidden_role in (' from anon', ' from authenticated', ' to anon', ' to authenticated'):
    require(not any(forbidden_role in stmt for stmt in migration + rollback), f'forbidden browser-role ACL mutation: {forbidden_role.strip()}')

revoke_names = {sig.split('(', 1)[0] for sig in revoke_signatures}
require(not (revoke_names & preserved_names), 'preserved service-role entry appears in revoke set')

for bff_path in (root / 'api' / 'crm.js', root / 'functions' / 'api' / 'crm.js'):
    source = bff_path.read_text(encoding='utf-8')
    require('const ALL_RPCS' in source, f'BFF allowlist anchor missing: {bff_path}')
    prefix = source.split('const ALL_RPCS', 1)[0]
    names = set(re.findall(r"['\"](crm_[a-z0-9_]+)['\"]", prefix))
    require(names == bff_names, f'BFF RPC entry set drift in {bff_path}: {sorted(names)}')
    require(not (names & revoke_names), f'BFF contains a proposed revoked direct RPC in {bff_path}')

for sql_path in (preflight_path, postcheck_path):
    raw = sql_path.read_text(encoding='utf-8')
    body = re.sub(r'--[^\n]*', '', raw)
    require(not re.search(r'(?im)^\s*(grant|revoke|create|alter|drop|insert|update|delete|truncate)\b', body), f'{sql_path.name} must remain read-only')
    require('crm_server_audit_logs_id_seq' in raw, f'{sql_path.name} lost sequence ACL preservation check')
    require('service_role' in raw and 'anon' in raw and 'authenticated' in raw, f'{sql_path.name} lost role boundary checks')
    require('fingerprint' in raw and 'inventory_lines' in raw, f'{sql_path.name} lost canonical fingerprint check')

preflight = preflight_path.read_text(encoding='utf-8')
postcheck = postcheck_path.read_text(encoding='utf-8')
require('revoke_candidate_service_exec' in preflight, 'preflight lost 28-candidate count')
require('unexpected_service_exec' in postcheck, 'post-check lost unexpected service-role count')

expected_current_fp = '40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df'
expected_new_fp = '625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691'
doc = doc_path.read_text(encoding='utf-8')
for marker, label in (
    ('main@9c4b0d8647da6f4544b563324a8d2c525165e74e', 'accepted main'),
    ('PUBLIC / anon / authenticated / service_role = 0 / 0 / 0 / 40', 'pre-apply function boundary'),
    ('20260823104232 / post_p5_revoke_browser_audit_sequence_acl', 'pre-apply migration'),
    (f'258 / {expected_current_fp}', 'pre-apply fingerprint'),
    ('20260823120150 / post_p5_minimize_service_role_rpc_exec', 'applied migration'),
    (f'258 / {expected_new_fp}', 'accepted fingerprint'),
    ('temporary service_role EXECUTE count: `12`', 'transaction rehearsal service count'),
    ('BFF-entry permission-denied tests: `0`', 'transaction rehearsal permission result'),
    ('`ROLLBACK`', 'transaction rollback'),
    ('already_initialized', 'bootstrap fail-closed guard'),
    ('`service_role EXECUTE = 12`', 'post-apply direct service-role count'),
    ('`42501 permission denied`', 'direct-internal denial smoke'),
    ('`INVALID_SESSION` (`P0001`)', 'wrapper nested-chain smoke'),
    ('production-change=applied+verified', 'Production acceptance state'),
):
    require(marker in doc, f'documentation missing {label}')

build = (root / 'build.sh').read_text(encoding='utf-8')
require(build.count('python3 test_post_p5_service_role_rpc_minimization.py') == 1, 'build must execute service-role minimization gate exactly once')

print(
    'POST_P5_SERVICE_ROLE_RPC_MINIMIZATION_OK: '
    'revoke=28-internal-service-role; preserved=11-bff+bootstrap; rollback=exact; '
    'service-role=12; direct-internal=denied; wrapper-chain=preserved; '
    'fingerprint=625be29b; production-change=applied+verified'
)
