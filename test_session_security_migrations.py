from pathlib import Path

root = Path(__file__).resolve().parent
unlock = (root / 'supabase/migrations/20260816_revoke_credential_unlocks_on_identity_change.sql').read_text(encoding='utf-8')
sessions = (root / 'supabase/migrations/20260816_limit_active_sessions_per_user.sql').read_text(encoding='utf-8')

required_unlock = (
    'crm_revoke_unlocks_on_user_security_change',
    'old.password_hash is distinct from new.password_hash',
    'old.enabled is distinct from new.enabled',
    'delete from public.crm_credential_unlocks where user_id=new.id',
    'crm_revoke_unlocks_on_membership_security_change',
    'old.role is distinct from new.role',
    'where user_id=new.user_id and workspace_id=new.workspace_id',
    'after update of password_hash, enabled on public.crm_users',
    'after update of role, enabled on public.crm_workspace_members',
)

required_sessions = (
    'crm_limit_active_sessions_per_user',
    'partition by s.user_id',
    'greatest(coalesce(s.last_seen_at,s.created_at),s.created_at) desc',
    'and r.rn>8',
    "'SESSION_PRUNED'",
    "'maxActiveSessions',8",
    'after insert on public.crm_sessions',
    'revoke all on function public.crm_limit_active_sessions_per_user() from public, anon, authenticated;',
)

missing = [x for x in required_unlock if x not in unlock]
missing += [x for x in required_sessions if x not in sessions]
if missing:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED missing: ' + ', '.join(missing))

if 'token_hash' in sessions and "jsonb_build_object('removedCount',v_removed,'maxActiveSessions',8)" not in sessions:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED session pruning audit shape changed')

print('SESSION_SECURITY_MIGRATIONS_TESTS_OK')
