from pathlib import Path

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260823_post_p5_crm_rls_alter_guard.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase' / 'rollback' / '20260823_post_p5_crm_rls_alter_guard.sql').read_text(encoding='utf-8')
preflight = (root / 'supabase' / 'baseline' / 'post_p5_crm_rls_alter_guard_preflight.sql').read_text(encoding='utf-8')
postcheck = (root / 'supabase' / 'baseline' / 'post_p5_crm_rls_alter_guard_check.sql').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'POST_P5_CRM_RLS_ALTER_GUARD.md').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, msg):
    if not ok:
        raise SystemExit(msg)

low = migration.lower()
require('create or replace function public.growthops_crm_rls_guard_ddl()' in low,
        'missing RLS guard function')
require('returns event_trigger' in low and 'security definer' in low and "set search_path to 'pg_catalog'" in low,
        'RLS guard must be SECURITY DEFINER with fixed pg_catalog search_path')
require("where schema_name='public'" in low and "object_type in ('table','partitioned table')" in low,
        'RLS guard lost public table scope')
require("like 'crm\\_%' escape '\\'" in migration,
        'RLS guard lost exact crm_ prefix filter')
require("not coalesce(v_rls,false)" in low,
        'RLS guard lost recursion-bounding relrowsecurity check')
require("alter table %s enable row level security" in low,
        'RLS guard lost ENABLE ROW LEVEL SECURITY action')
require('revoke execute on function public.growthops_crm_rls_guard_ddl()' in low,
        'RLS guard external EXECUTE revoke missing')
require('create event trigger growthops_crm_rls_guard_ddl' in low and "when tag in ('alter table')" in low,
        'RLS guard must listen exactly to ALTER TABLE')
require('alter default privileges' not in low,
        'RLS guard must not alter global/default privileges')
require('growthops_crm_acl_guard_ddl' not in low,
        'RLS guard migration must not replace the ACL guard')
require('ensure_rls' not in low,
        'RLS guard migration must not replace the create-time RLS guard')

rb = rollback.lower()
require('drop event trigger if exists growthops_crm_rls_guard_ddl;' in rb,
        'rollback missing event-trigger drop')
require('drop function if exists public.growthops_crm_rls_guard_ddl();' in rb,
        'rollback missing function drop')
for forbidden in ('grant ', 'revoke ', 'create ', 'alter default privileges'):
    require(forbidden not in rb, f'rollback must not broaden/recreate privileges: {forbidden.strip()}')

for sql,label in ((preflight.lower(),'preflight'),(postcheck.lower(),'post-check')):
    for forbidden in ('create ', 'drop ', 'alter ', 'grant ', 'revoke ', 'truncate ', 'delete from ', 'insert into ', 'update public.'):
        require(forbidden not in sql, f'{label} is no longer read-only: {forbidden.strip()}')
    require('inventory_lines' in sql and 'fingerprint' in sql, f'{label} lost canonical verification')

for expected,label in (
    ('c22750d639d1b08a6e6f387f889d6de62b5c2ca7','accepted predecessor main'),
    ('20260823135410 / post_p5_crm_acl_event_guard','accepted predecessor migration'),
    ('195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e','stable canonical'),
    ('Production change: **not applied**','preparation status'),
    ('SET SCHEMA','schema-move rehearsal'),
    ('rename-to-`crm_*`','rename rehearsal'),
):
    require(expected in doc, f'doc missing {label}')

require(build.count('python3 test_post_p5_crm_rls_alter_guard.py') == 1,
        'build must run CRM RLS ALTER guard gate exactly once')

print(
    'POST_P5_CRM_RLS_ALTER_GUARD_OK: '
    'scope=public.crm_*+ALTER_TABLE; set-schema=covered; rename=covered; '
    'create-rls-guard=preserved; acl-guard=preserved; fingerprint=a69eba75; '
    'production-change=none'
)
