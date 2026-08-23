from pathlib import Path
import re

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260823_post_p5_crm_acl_event_guard.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase' / 'rollback' / '20260823_post_p5_crm_acl_event_guard.sql').read_text(encoding='utf-8')
preflight = (root / 'supabase' / 'baseline' / 'post_p5_crm_acl_event_guard_preflight.sql').read_text(encoding='utf-8')
postcheck = (root / 'supabase' / 'baseline' / 'post_p5_crm_acl_event_guard_check.sql').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'POST_P5_CRM_ACL_EVENT_GUARD.md').read_text(encoding='utf-8')
vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, msg):
    if not ok:
        raise SystemExit(msg)


allowed = {
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
bff_expected = allowed - {'crm_bootstrap_admin'}

require('create or replace function public.growthops_crm_acl_guard_ddl()' in migration.lower(),
        'missing infrastructure guard function')
require('security definer' in migration.lower() and "set search_path to 'pg_catalog'" in migration.lower(),
        'guard must be SECURITY DEFINER with fixed pg_catalog search_path')
require('create event trigger growthops_crm_acl_guard_ddl' in migration.lower(),
        'missing CRM ACL event trigger')
require('alter default privileges' not in migration.lower(),
        'guard package must not alter global/default privileges')
require("like 'crm\\_%' escape '\\'" in migration,
        'guard lost exact crm_ prefix filter')
require('revoke execute on function %s from public, anon, authenticated' in migration.lower(),
        'function browser-role revoke missing')
require('revoke execute on procedure %s from public, anon, authenticated, service_role' in migration.lower(),
        'procedure fail-closed revoke missing')
require('revoke all privileges on table %s from public, anon, authenticated, service_role' in migration.lower(),
        'relation fail-closed revoke missing')
require('revoke all privileges on sequence %s from public, anon, authenticated, service_role' in migration.lower(),
        'sequence fail-closed revoke missing')
require('revoke execute on function public.growthops_crm_acl_guard_ddl()' in migration.lower(),
        'guard function external EXECUTE revoke missing')

for tag in (
    'CREATE FUNCTION','ALTER FUNCTION','CREATE PROCEDURE','ALTER PROCEDURE',
    'CREATE TABLE','ALTER TABLE','CREATE TABLE AS','SELECT INTO',
    'CREATE SEQUENCE','ALTER SEQUENCE','CREATE VIEW','ALTER VIEW',
    'CREATE MATERIALIZED VIEW','ALTER MATERIALIZED VIEW',
    'CREATE FOREIGN TABLE','ALTER FOREIGN TABLE',
):
    require(f"'{tag}'" in migration, f'missing DDL guard tag: {tag}')

found_allowed = set(re.findall(r"v_name='(crm_[a-z0-9_]+)'", migration))
require(found_allowed == allowed, f'service-role allowlist drift: {sorted(found_allowed ^ allowed)}')

required_signature_clauses = (
    "v_name='crm_bootstrap_admin' and v_args='p_setup_code text, p_name text, p_username text, p_password text'",
    "v_name='crm_client_account_safe_summary' and v_args='p_token text, p_client_id text'",
    "v_name='crm_delete_user' and v_args='p_token text, p_user_id uuid'",
    "v_name='crm_list_users' and v_args='p_token text'",
    "v_name='crm_load_state_v3' and v_args='p_token text'",
    "v_name='crm_login_v3' and v_args='p_username text, p_password text'",
    "v_name='crm_logout' and v_args='p_token text'",
    "v_name='crm_public_status' and v_args=''",
    "v_name='crm_reveal_client_secret_value_v5' and v_args='p_token text, p_unlock_token text, p_client_id text, p_platform text, p_account_id text, p_field text'",
    "v_name='crm_save_state' and v_args='p_token text, p_state jsonb, p_expected_revision bigint'",
    "v_name='crm_unlock_credentials_v1' and v_args='p_token text, p_password text'",
    "v_name='crm_upsert_user' and v_args='p_token text, p_user_id uuid, p_name text, p_username text, p_password text, p_role text, p_enabled boolean'",
)
for clause in required_signature_clauses:
    require(clause in migration, f'missing exact service allowlist signature: {clause}')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    names = set(re.findall(r"'(crm_[a-z0-9_]+)'", source))
    require(names == bff_expected, f'{label} BFF RPC set drift: {sorted(names ^ bff_expected)}')

rb = rollback.lower()
require('drop event trigger if exists growthops_crm_acl_guard_ddl;' in rb,
        'rollback missing event-trigger drop')
require('drop function if exists public.growthops_crm_acl_guard_ddl();' in rb,
        'rollback missing guard-function drop')
for forbidden in ('grant ', 'revoke ', 'alter default privileges', 'create '):
    require(forbidden not in rb, f'rollback must not broaden/recreate ACL state: {forbidden.strip()}')

for sql, label in ((preflight.lower(), 'preflight'), (postcheck.lower(), 'post-check')):
    for forbidden in ('create ', 'drop ', 'alter ', 'grant ', 'revoke ', 'truncate ', 'delete from ', 'insert into ', 'update public.'):
        require(forbidden not in sql, f'{label} is no longer read-only: {forbidden.strip()}')
    require('inventory_lines' in sql and 'fingerprint' in sql, f'{label} lost canonical verification')

for expected, label in (
    ('cb466292535508325fadb7ebe0ba1626755f1e3c', 'accepted predecessor main'),
    ('20260823131002 / post_p5_login_trusted_source_bucket', 'accepted predecessor migration'),
    ('195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e', 'stable canonical'),
    ('Production change: **not applied**', 'preparation status'),
    ('CREATE and ALTER/rename paths are both covered', 'rename bypass coverage'),
    ('explicit service-role opt-in after creation = true', 'service opt-in rehearsal'),
):
    require(expected in doc, f'doc missing {label}')

require(build.count('python3 test_post_p5_crm_acl_event_guard.py') == 1,
        'build must run CRM ACL event-guard gate exactly once')

print(
    'POST_P5_CRM_ACL_EVENT_GUARD_OK: '
    'scope=public.crm_*; create+alter=covered; procedures=deny; '
    'service-allowlist=12; relations=deny; default-privileges=unchanged; '
    'fingerprint=a69eba75; production-change=none'
)
