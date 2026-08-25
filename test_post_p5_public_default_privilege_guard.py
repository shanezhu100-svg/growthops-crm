from pathlib import Path
import re

root = Path(__file__).resolve().parent
migration_path = root / 'supabase' / 'migrations' / '20260824_post_p5_public_default_privilege_guard.sql'
rollback_path = root / 'supabase' / 'rollback' / '20260824_post_p5_public_default_privilege_guard.sql'
preflight_path = root / 'supabase' / 'baseline' / 'post_p5_public_default_privilege_guard_preflight.sql'
postcheck_path = root / 'supabase' / 'baseline' / 'post_p5_public_default_privilege_guard_check.sql'
probe_path = root / 'supabase' / 'baseline' / 'post_p5_public_default_privilege_guard_probe.sql'
fingerprint_path = root / 'supabase' / 'baseline' / 'post_p5_crm_guard_security_fingerprint.sql'
current_state_path = root / 'docs' / 'cloudflare-migration' / 'CURRENT_STATE.md'
current_recovery_path = root / 'docs' / 'cloudflare-migration' / 'CURRENT_RECOVERY_VERIFICATION.md'
guard_doc_path = root / 'docs' / 'cloudflare-migration' / 'POST_P5_GUARD_FINGERPRINT.md'
ledger_path = root / 'docs' / 'cloudflare-migration' / 'P0_MIGRATION_LEDGER.md'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def strip_comments(text):
    return re.sub(r'--[^\n]*', '', text)


migration = migration_path.read_text(encoding='utf-8')
rollback = rollback_path.read_text(encoding='utf-8')
preflight = preflight_path.read_text(encoding='utf-8')
postcheck = postcheck_path.read_text(encoding='utf-8')
probe = probe_path.read_text(encoding='utf-8')
fingerprint = fingerprint_path.read_text(encoding='utf-8')
current_state = current_state_path.read_text(encoding='utf-8')
current_recovery = current_recovery_path.read_text(encoding='utf-8')
guard_doc = guard_doc_path.read_text(encoding='utf-8')
ledger = ledger_path.read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')
existing_function_boundary = (root / 'test_post_p5_public_function_exec_boundary.py').read_text(encoding='utf-8')
existing_crm_guard = (root / 'supabase' / 'migrations' / '20260823_post_p5_crm_acl_event_guard.sql').read_text(encoding='utf-8')

m = migration.lower()
r = rollback.lower()

# Default-privilege scope must be postgres + public only. Never alter Supabase
# platform-role defaults or other schemas from this GrowthOps package.
require(m.count('alter default privileges for role postgres in schema public') == 3,
        'migration must contain exactly three postgres/public default-privilege changes')
require('for role supabase_admin' not in m, 'migration must not alter supabase_admin defaults')
for schema in ('extensions', 'storage', 'graphql', 'graphql_public', 'realtime', 'auth'):
    require(f'in schema {schema}' not in m, f'migration must not alter platform schema: {schema}')
require('revoke all privileges on tables from service_role' in m,
        'future public tables must default-deny service_role')
require('revoke all privileges on sequences from service_role' in m,
        'future public sequences must default-deny service_role')
require('revoke execute on functions from service_role' in m,
        'future public functions must not auto-grant service_role')

# PostgreSQL hard-wired PUBLIC EXECUTE on new functions is closed by a public-only
# event trigger rather than by a global postgres default-privilege change.
require('create or replace function public.growthops_public_noncrm_function_acl_guard_ddl()' in m,
        'missing non-CRM public function ACL guard')
require('returns event_trigger' in m and 'security definer' in m and "set search_path to 'pg_catalog'" in m,
        'non-CRM guard must be event_trigger SECURITY DEFINER with fixed pg_catalog search_path')
require("where schema_name = 'public'" in m, 'guard lost public schema boundary')
require("not like 'crm\\_%' escape '\\'" in migration,
        'guard must exclude crm_ functions handled by the existing exact allowlist guard')
for target in ('function', 'procedure'):
    require(
        f'revoke execute on {target} %s from public, anon, authenticated, service_role' in m,
        f'guard missing fail-closed {target} revoke'
    )
for tag in ('CREATE FUNCTION', 'ALTER FUNCTION', 'CREATE PROCEDURE', 'ALTER PROCEDURE'):
    require(f"'{tag}'" in migration, f'event trigger missing tag: {tag}')
require('revoke execute on function public.growthops_public_noncrm_function_acl_guard_ddl()' in m,
        'guard function itself must be externally non-executable')

# Exact rollback restores only the pre-migration service_role defaults and removes
# only the new guard. It must not broaden anon/authenticated/PUBLIC explicitly.
require('drop event trigger if exists growthops_public_noncrm_function_acl_guard_ddl' in r,
        'rollback missing event-trigger drop')
require('drop function if exists public.growthops_public_noncrm_function_acl_guard_ddl()' in r,
        'rollback missing guard-function drop')
require(r.count('alter default privileges for role postgres in schema public') == 3,
        'rollback must restore exactly three postgres/public default classes')
require('grant all privileges on tables to service_role' in r,
        'rollback missing table default restoration')
require('grant all privileges on sequences to service_role' in r,
        'rollback missing sequence default restoration')
require('grant execute on functions to service_role' in r,
        'rollback missing function default restoration')
for grantee in ('anon', 'authenticated', 'public'):
    require(not re.search(rf'grant[^;]+\bto\s+{grantee}\b', r),
            f'rollback must not add explicit {grantee} grants')

# Preflight and post-check must remain read-only catalog checks.
for sql_path, raw in ((preflight_path, preflight), (postcheck_path, postcheck)):
    body = strip_comments(raw)
    require(not re.search(
        r'(?im)^\s*(grant|revoke|create|alter|drop|insert|update|delete|truncate|do|begin|commit|rollback)\b',
        body
    ), f'{sql_path.name} must remain read-only')
    for marker in (
        "pg_get_userbyid(d.defaclrole) = 'postgres'",
        "n.nspname = 'public'",
        "has_function_privilege('anon'",
        "has_function_privilege('authenticated'",
        "has_function_privilege('service_role'",
    ):
        require(marker in raw, f'{sql_path.name} missing boundary marker: {marker}')

for marker in (
    'table_default_service_role_grants',
    'sequence_default_service_role_grants',
    'function_default_service_role_grants',
    'noncrm_app_executable',
    "p.proname = 'growthops_public_noncrm_function_acl_guard_ddl'",
    "e.evtname = 'growthops_public_noncrm_function_acl_guard_ddl'",
    'service_role_direct_relation_grants',
    'service_role_direct_sequence_grants',
):
    require(marker in postcheck, f'post-check missing target marker: {marker}')

# The acceptance probe is intentionally mutating, but must be transaction-contained,
# assert effective privileges, roll back, and prove every probe object disappeared.
p = strip_comments(probe).lower()
require(len(re.findall(r'(?im)^\s*begin\s*;', p)) == 1, 'probe must start exactly one transaction')
require(len(re.findall(r'(?im)^\s*rollback\s*;', p)) == 1, 'probe must roll back exactly once')
require(not re.search(r'(?im)^\s*commit\b', p), 'probe must never COMMIT')
for name in (
    'growthops_public_acl_probe_table_20260824',
    'growthops_public_acl_probe_sequence_20260824',
    'growthops_public_acl_probe_function_20260824',
):
    require(name in p, f'probe missing object: {name}')
for role in ('anon', 'authenticated', 'service_role'):
    require(f"has_function_privilege('{role}'" in p, f'probe missing {role} function effective-EXECUTE check')
require('x.grantee = 0' in p and "x.privilege_type = 'execute'" in p,
        'probe must explicitly detect PUBLIC EXECUTE ACL')
for privilege in ('select', 'insert', 'update', 'delete', 'truncate', 'references', 'trigger'):
    require(f"has_table_privilege('service_role'" in p and f"'{privilege.upper()}'" in probe,
            f'probe missing table service_role privilege check: {privilege}')
for privilege in ('USAGE', 'SELECT', 'UPDATE'):
    require(f"'{privilege}'" in probe, f'probe missing sequence service_role privilege check: {privilege}')
for marker in ('table_rolled_back', 'sequence_rolled_back', 'function_rolled_back'):
    require(marker in p, f'probe missing rollback proof: {marker}')

# Preserve the already-accepted current function surface and CRM-specific guard.
require('service-role-target=12' in existing_function_boundary,
        'all-public function boundary target drifted from 12')
require("like 'crm\\_%' escape '\\'" in existing_crm_guard,
        'existing CRM guard lost crm_ prefix authority')
require(build.count('python3 test_post_p5_public_default_privilege_guard.py') == 1,
        'build must execute public default-privilege guard gate exactly once')

# Stage-C current-state authority must match the freshly verified Production state.
new_guard = 'growthops_public_noncrm_function_acl_guard_ddl'
new_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'
new_migration = '20260825040850 / post_p5_public_default_privilege_guard'
for source, label in (
    (fingerprint, 'guard fingerprint SQL'),
    (guard_doc, 'guard fingerprint documentation'),
    (current_state, 'current state'),
    (current_recovery, 'current recovery verification'),
):
    require(new_guard in source, f'{label} missing third guard')
    require(new_hash in source, f'{label} missing accepted three-guard fingerprint')
    require('guard_inventory_lines = 9' in source or 'guard inventory lines: `9`' in source,
            f'{label} missing guard inventory count 9')

require(new_migration in current_state,
        'CURRENT_STATE missing latest accepted Production migration')
require(new_migration in current_recovery,
        'CURRENT_RECOVERY_VERIFICATION missing latest accepted Production migration')
require('postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`' in current_state,
        'CURRENT_STATE missing future default service-role boundary')
require('future-object default-privilege hardening' in current_recovery,
        'CURRENT_RECOVERY_VERIFICATION missing future-object acceptance context')
require('20260825040850' in ledger and
        'post_p5_public_default_privilege_guard' in ledger and
        'supabase/migrations/20260824_post_p5_public_default_privilege_guard.sql' in ledger,
        'migration ledger missing applied #78 mapping')

print(
    'POST_P5_PUBLIC_DEFAULT_PRIVILEGE_GUARD_PACKAGE_OK: '
    'postgres-public=service-default-deny; noncrm-function=event-guard; '
    'crm-allowlist=preserved; supabase-platform-schemas=untouched; '
    'probe=transactional-rollback; production-change=applied+verified'
)
