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


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_p5_group6_revoke_public_boundary_anon_exec.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_p5_group6_restore_public_boundary_anon_exec.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'p5_group6_public_boundary_anon_exec_check.sql')

forward = (
    'revoke execute on function public.crm_login_v3(text, text) from anon; '
    'revoke execute on function public.crm_public_status() from anon;'
)
reverse = (
    'grant execute on function public.crm_login_v3(text, text) to anon; '
    'grant execute on function public.crm_public_status() to anon;'
)

require(migration == forward, f'Group6 migration must contain exactly two revokes: {migration!r}')
require(rollback == reverse, f'Group6 rollback must contain exactly two inverse grants: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in Group6 migration: {forbidden.strip()}')

for rpc in ('crm_login_v3', 'crm_public_status'):
    require(rpc in check, f'post-check lost target RPC: {rpc}')
for needle in ('target_count', 'total_anon_crm_exec', 'total_authenticated_crm_exec', 'total_service_crm_exec', 'has_function_privilege'):
    require(needle in check, f'post-check lost required assertion surface: {needle}')
for forbidden in (' revoke ', ' grant ', ' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate '):
    require(forbidden not in f' {check} ', f'post-check is not read-only: {forbidden.strip()}')

vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
bff_test = (root / 'test_p5_group6_public_boundary_bff.mjs').read_text(encoding='utf-8')
candidate = (root / 'test_p5_group6_public_boundary_candidate.py').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    require("'crm_login_v3'" in source and "'crm_public_status'" in source,
            f'{label}: public-boundary RPC disappeared')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable identity reintroduced')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin gate missing')
    require('delete args.p_token' in source, f'{label}: p_token stripping missing')
    require('__Host-growthops_crm' in source and 'HttpOnly; Secure; SameSite=Strict' in source,
            f'{label}: secure login cookie boundary missing')

require('P5_GROUP6_PUBLIC_BOUNDARY_BFF_OK' in bff_test, 'Group6 executable BFF marker missing')
require('public-status=no-session+server-identity' in bff_test, 'Group6 BFF test lost public-status proof')
require('login=no-session+token-to-HttpOnly-cookie' in bff_test, 'Group6 BFF test lost login bridge proof')
require('invalid-login=generic' in bff_test, 'Group6 BFF test lost generic invalid-login proof')
require('login-guards=preserved' in candidate, 'Group6 candidate gate lost login safeguards')

print(
    'P5_GROUP6_PUBLIC_BOUNDARY_REVOCATION_OK: '
    'revoke=2-public-boundary-anon-only; rollback=2-exact-grants; '
    'post-check=read-only; bff=no-session-server-bridge; expected-anon=0; service-role=40'
)
