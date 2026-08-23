from pathlib import Path

migration = Path('supabase/migrations/20260822_p5_revoke_sensitive_anon_exec.sql').read_text().lower()
rollback = Path('supabase/rollback/20260822_p5_restore_sensitive_anon_exec.sql').read_text().lower()
check = Path('supabase/baseline/p5_sensitive_anon_exec_check.sql').read_text().lower()
vercel = Path('api/crm.js').read_text()
cloudflare = Path('functions/api/crm.js').read_text()

unlock_sig = 'public.crm_unlock_credentials_v1(text, text)'
reveal_sig = 'public.crm_reveal_client_secret_value_v5(text, text, text, text, text, text)'

# Migration scope: exactly two anon revokes, no function/runtime/schema/data changes.
assert migration.count('revoke execute on function') == 2
assert f'revoke execute on function {unlock_sig} from anon;' in migration
assert f'revoke execute on function {reveal_sig} from anon;' in migration
assert migration.count(' from anon;') == 2
assert 'grant execute' not in migration
for forbidden in (
    'create or replace function', 'alter function', 'drop function',
    'revoke execute on function public.crm_login_v3',
    'revoke execute on function public.crm_public_status',
    'revoke execute on function public.crm_load_state_v3',
    'revoke execute on function public.crm_save_state',
    'revoke execute on function public.crm_logout',
    'revoke execute on function public.crm_list_users',
    'revoke execute on function public.crm_upsert_user',
    'revoke execute on function public.crm_delete_user',
    'revoke execute on function public.crm_client_account_safe_summary',
    'insert into ', 'update public.', 'delete from ', 'truncate ',
):
    assert forbidden not in migration, forbidden

# Rollback scope: restore exactly those two anon grants and nothing else.
assert rollback.count('grant execute on function') == 2
assert f'grant execute on function {unlock_sig} to anon;' in rollback
assert f'grant execute on function {reveal_sig} to anon;' in rollback
assert rollback.count(' to anon;') == 2
assert 'revoke execute' not in rollback

# Read-only acceptance query must encode the expected post-P5 shape.
for marker in (
    'sensitive_anon_exec', 'sensitive_authenticated_exec',
    'sensitive_service_exec', 'total_anon_crm_exec', 'total_service_crm_exec',
    "crm_unlock_credentials_v1", "crm_reveal_client_secret_value_v5",
):
    assert marker in check
for forbidden in ('revoke ', 'grant ', 'insert ', 'update ', 'delete ', 'truncate ', 'alter ', 'drop '):
    # comments may mention words; only reject executable-looking statements at line starts.
    assert not any(line.strip().startswith(forbidden) for line in check.splitlines())

# Both rollback paths must continue to proxy the sensitive RPCs through the
# backend-only server identity after anon execution is removed.
for source in (vercel, cloudflare):
    assert 'GROWTHOPS_SUPABASE_SECRET_KEY' in source
    assert 'crm_unlock_credentials_v1' in source
    assert 'crm_reveal_client_secret_value_v5' in source
    assert 'GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source
    assert 'sb_publishable_' not in source

print('P5_SENSITIVE_RPC_REVOCATION_GATE_OK: revoke=2-sensitive-anon-only; rollback=2-exact-grants; server-identity=preserved; runtime=unchanged')
