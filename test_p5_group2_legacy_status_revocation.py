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


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_p5_group2_revoke_legacy_credential_status_anon_exec.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_p5_group2_restore_legacy_credential_status_anon_exec.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'p5_group2_legacy_status_anon_exec_check.sql')

forward_stmt = 'revoke execute on function public.crm_client_credential_status(text, text) from anon;'
rollback_stmt = 'grant execute on function public.crm_client_credential_status(text, text) to anon;'

require(migration == forward_stmt, f'Group2 migration must contain exactly one revoke: {migration!r}')
require(rollback == rollback_stmt, f'Group2 rollback must contain exactly one inverse grant: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in Group2 migration: {forbidden.strip()}')

require('crm_client_credential_status' in check, 'post-check lost target RPC')
require('total_anon_crm_exec' in check, 'post-check lost anon total')
require('total_service_crm_exec' in check, 'post-check lost service total')
require('has_function_privilege' in check, 'post-check must inspect effective EXECUTE privileges')
for forbidden in (' revoke ', ' grant ', ' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete ', ' truncate '):
    require(forbidden not in f' {check} ', f'post-check is not read-only: {forbidden.strip()}')

vercel_bff = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare_bff = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
v6_finalizer = (root / 'credential_ui_v6_finalize.py').read_text(encoding='utf-8')
legacy_rpc = 'crm_client_credential_status'
safe_summary = 'crm_client_account_safe_summary'

require(legacy_rpc not in vercel_bff, 'legacy status RPC unexpectedly reachable through Vercel BFF')
require(legacy_rpc not in cloudflare_bff, 'legacy status RPC unexpectedly reachable through Cloudflare BFF')
require(f'"{legacy_rpc}"' in v6_finalizer, 'v6 finalizer no longer explicitly forbids legacy status RPC')
require(safe_summary in vercel_bff and safe_summary in cloudflare_bff, 'safe-summary replacement must remain BFF reachable')
require(safe_summary in v6_finalizer, 'safe-summary replacement missing from final runtime gate')

print(
    'P5_GROUP2_LEGACY_STATUS_REVOCATION_OK: '
    'revoke=1-legacy-anon-only; rollback=1-exact-grant; '
    'post-check=read-only; expected-anon=9; service-role=40'
)
