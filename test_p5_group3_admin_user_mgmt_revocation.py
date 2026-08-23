from pathlib import Path
import re

root = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def sql_body(path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'--[^\n]*', '', text)
    return ' '.join(text.lower().split())


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_p5_group3_revoke_admin_user_mgmt_anon_exec.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_p5_group3_restore_admin_user_mgmt_anon_exec.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'p5_group3_admin_user_mgmt_anon_exec_check.sql')

forward = (
    'revoke execute on function public.crm_list_users(text) from anon; '
    'revoke execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) from anon; '
    'revoke execute on function public.crm_delete_user(text, uuid) from anon;'
)
reverse = (
    'grant execute on function public.crm_list_users(text) to anon; '
    'grant execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) to anon; '
    'grant execute on function public.crm_delete_user(text, uuid) to anon;'
)

require(migration == forward, f'Group3 migration must contain exactly three revokes: {migration!r}')
require(rollback == reverse, f'Group3 rollback must contain exactly three inverse grants: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in Group3 migration: {forbidden.strip()}')

admin_rpcs = ('crm_list_users', 'crm_upsert_user', 'crm_delete_user')
for rpc in admin_rpcs:
    require(rpc in check, f'post-check lost target RPC: {rpc}')
require('target_count' in check, 'post-check lost target count')
require('total_anon_crm_exec' in check, 'post-check lost anon total')
require('total_authenticated_crm_exec' in check, 'post-check lost authenticated total')
require('total_service_crm_exec' in check, 'post-check lost service total')
require('has_function_privilege' in check, 'post-check must inspect effective EXECUTE privileges')
for forbidden in (' revoke ', ' grant ', ' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate '):
    require(forbidden not in f' {check} ', f'post-check is not read-only: {forbidden.strip()}')

vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
p2b = (root / 'test_cloudflare_p2b_api.mjs').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    for rpc in admin_rpcs:
        require(f"'{rpc}'" in source, f'{label} BFF lost {rpc}')
    require('__Host-growthops_crm' in source, f'{label} lost HttpOnly CRM cookie boundary')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label} lost server secret identity')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label} reintroduced publishable identity')
    require('SESSION_REQUIRED' in source, f'{label} lost session-required auth gate')

require('admin-user-rpcs=session-gated' in p2b,
        'cross-platform dynamic ADMIN RPC session gate missing')
for rpc in admin_rpcs:
    require(f"rpc:'{rpc}'" in p2b, f'cross-platform dynamic test lost {rpc}')

print(
    'P5_GROUP3_ADMIN_USER_MGMT_REVOCATION_OK: '
    'revoke=3-admin-anon-only; rollback=3-exact-grants; '
    'post-check=read-only; auth-bff=session-gated; expected-anon=6; service-role=40'
)
