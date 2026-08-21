from pathlib import Path

root = Path(__file__).resolve().parent
unlock = (root / 'supabase/migrations/20260816_revoke_credential_unlocks_on_identity_change.sql').read_text(encoding='utf-8')
legacy_sessions = (root / 'supabase/migrations/20260816_limit_active_sessions_per_user.sql').read_text(encoding='utf-8')
hardening = (root / 'supabase/migrations/20260821_credential_surface_session_hardening.sql').read_text(encoding='utf-8')

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

required_legacy_sessions = (
    'crm_limit_active_sessions_per_user',
    'partition by s.user_id',
    'after insert on public.crm_sessions',
)

required_hardening = (
    'crm_cap_session_expiry_v2',
    "interval '7 days'",
    'before insert or update of expires_at on public.crm_sessions',
    "set expires_at = now() + interval '7 days'",
    'crm_limit_active_sessions_per_user',
    'partition by s.user_id',
    'greatest(coalesce(s.last_seen_at,s.created_at),s.created_at) desc',
    'and r.rn>4',
    "'SESSION_PRUNED'",
    "'maxActiveSessions',4",
    'after insert on public.crm_sessions',
    "'reason','SECURITY_HARDENING'",
    'max(workspace_id::text)::uuid as workspace_id',
    'revoke all on function public.crm_cap_session_expiry_v2() from public, anon, authenticated;',
    'revoke all on function public.crm_limit_active_sessions_per_user() from public, anon, authenticated;',
)

missing = [x for x in required_unlock if x not in unlock]
missing += [x for x in required_legacy_sessions if x not in legacy_sessions]
missing += [x for x in required_hardening if x not in hardening]
if missing:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED missing: ' + ', '.join(missing))

if "jsonb_build_object('removedCount',v_removed,'maxActiveSessions',4)" not in hardening:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED four-session pruning audit shape changed')
if 'and r.rn>8' in hardening or "'maxActiveSessions',8" in hardening:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED old eight-session limit survived final hardening')
if "interval '30 days'" in hardening:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED 30-day session lifetime survived final hardening')
if 'min(workspace_id)' in hardening:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED unsupported min(uuid) aggregation returned')

print('SESSION_SECURITY_MIGRATIONS_TESTS_OK: max_session_age=7d; max_active_sessions=4; uuid_aggregation=valid')
