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


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_p5_group4_revoke_safe_summary_anon_exec.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_p5_group4_restore_safe_summary_anon_exec.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'p5_group4_safe_summary_anon_exec_check.sql')

forward = 'revoke execute on function public.crm_client_account_safe_summary(text, text) from anon;'
reverse = 'grant execute on function public.crm_client_account_safe_summary(text, text) to anon;'

require(migration == forward, f'Group4 migration must contain exactly one safe-summary revoke: {migration!r}')
require(rollback == reverse, f'Group4 rollback must contain exactly one inverse grant: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in Group4 migration: {forbidden.strip()}')

require('crm_client_account_safe_summary' in check, 'post-check lost safe-summary target')
require('target_count' in check, 'post-check lost target count')
require('total_anon_crm_exec' in check, 'post-check lost anon total')
require('total_authenticated_crm_exec' in check, 'post-check lost authenticated total')
require('total_service_crm_exec' in check, 'post-check lost service total')
require('has_function_privilege' in check, 'post-check must inspect effective EXECUTE privileges')
for forbidden in (' revoke ', ' grant ', ' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete from ', ' truncate '):
    require(forbidden not in f' {check} ', f'post-check is not read-only: {forbidden.strip()}')

vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
bff_test = (root / 'test_p5_group4_safe_summary_bff.mjs').read_text(encoding='utf-8')
candidate = (root / 'test_p5_group4_safe_summary_candidate.py').read_text(encoding='utf-8')
rpc = 'crm_client_account_safe_summary'

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    require(f"'{rpc}'" in source, f'{label} BFF lost safe-summary RPC')
    require('__Host-growthops_crm' in source, f'{label} lost HttpOnly CRM cookie boundary')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label} lost server secret identity')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label} reintroduced publishable identity')
    require('SESSION_REQUIRED' in source, f'{label} lost session-required auth gate')

require('P5_GROUP4_SAFE_SUMMARY_BFF_OK' in bff_test, 'Group4 executable BFF marker missing')
require('no-session=401+zero-upstream' in bff_test, 'Group4 BFF test lost no-session/zero-upstream proof')
require('cookie-token=authoritative' in bff_test, 'Group4 BFF test lost cookie-token authority proof')
require('output=identifier+presence-booleans-only' in candidate,
        'Group4 candidate gate lost narrow safe-summary output contract')
require('reveal-call=none' in candidate, 'Group4 candidate gate lost no-reveal contract')

print(
    'P5_GROUP4_SAFE_SUMMARY_REVOCATION_OK: '
    'revoke=1-safe-summary-anon-only; rollback=1-exact-grant; '
    'post-check=read-only; auth-bff=session-gated; expected-anon=5; service-role=40'
)
