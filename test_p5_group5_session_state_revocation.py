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


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_p5_group5_revoke_session_state_anon_exec.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_p5_group5_restore_session_state_anon_exec.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'p5_group5_session_state_anon_exec_check.sql')

forward = (
    'revoke execute on function public.crm_load_state_v3(text) from anon; '
    'revoke execute on function public.crm_save_state(text, jsonb, bigint) from anon; '
    'revoke execute on function public.crm_logout(text) from anon;'
)
reverse = (
    'grant execute on function public.crm_load_state_v3(text) to anon; '
    'grant execute on function public.crm_save_state(text, jsonb, bigint) to anon; '
    'grant execute on function public.crm_logout(text) to anon;'
)

require(migration == forward, f'Group5 migration must contain exactly three revokes: {migration!r}')
require(rollback == reverse, f'Group5 rollback must contain exactly three inverse grants: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in Group5 migration: {forbidden.strip()}')

for rpc in ('crm_load_state_v3', 'crm_save_state', 'crm_logout'):
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
bff_test = (root / 'test_p5_group5_session_state_bff.mjs').read_text(encoding='utf-8')
candidate = (root / 'test_p5_group5_session_state_candidate.py').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    for rpc in ('crm_load_state_v3', 'crm_save_state', 'crm_logout'):
        require(f"'{rpc}'" in source, f'{label} BFF lost {rpc}')
    require('__Host-growthops_crm' in source, f'{label} lost HttpOnly CRM cookie boundary')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label} lost server secret identity')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label} reintroduced publishable identity')
    require('SESSION_REQUIRED' in source, f'{label} lost session-required auth gate')

require('P5_GROUP5_SESSION_STATE_BFF_OK' in bff_test, 'Group5 executable BFF marker missing')
require('no-session-zero-upstream' in bff_test, 'Group5 BFF test lost no-session/zero-upstream proof')
require('cookie-token=authoritative' in bff_test, 'Group5 BFF test lost cookie-token authority proof')
require('logout-success=clears-cookie' in bff_test, 'Group5 BFF test lost logout success cookie-clear proof')
require('save-secret-guard=covered' in candidate, 'Group5 candidate gate lost save-state secret guard')
require('logout-distinction=preserved' in candidate, 'Group5 candidate gate lost logout distinction')

print(
    'P5_GROUP5_SESSION_STATE_REVOCATION_OK: '
    'revoke=3-session-state-anon-only; rollback=3-exact-grants; '
    'post-check=read-only; auth-bff=session-gated; expected-anon=2; service-role=40'
)
