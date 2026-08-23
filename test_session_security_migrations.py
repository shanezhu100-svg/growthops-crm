from pathlib import Path

root = Path(__file__).resolve().parent
unlock = (root / 'supabase/migrations/20260816_revoke_credential_unlocks_on_identity_change.sql').read_text(encoding='utf-8')
legacy_sessions = (root / 'supabase/migrations/20260816_limit_active_sessions_per_user.sql').read_text(encoding='utf-8')
hardening = (root / 'supabase/migrations/20260821_credential_surface_session_hardening.sql').read_text(encoding='utf-8')
reauth_bridge = (root / 'supabase/migrations/20260823_credential_unlock_reauth_bridge.sql').read_text(encoding='utf-8')

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

required_reauth_bridge = (
    'create or replace function public.crm_reveal_client_secret_field_v3(',
    "if c.role <> 'ADMIN' then",
    "if v_platform not in ('facebook','tiktok','google','instagram') then",
    'v_session_hash text := public.crm_token_hash(p_token);',
    'v_has_recent_unlock boolean := false;',
    'from public.crm_credential_unlocks u',
    'where u.session_token_hash = v_session_hash',
    'and u.user_id = c.user_id',
    'and u.workspace_id = c.workspace_id',
    'and u.expires_at > now()',
    "v_session_created < now() - interval '12 hours' and not v_has_recent_unlock",
    "v_recent_5m >= 10 or v_recent_1h >= 40",
    "'REVEAL_CLIENT_SECRET_FIELD'",
    'public.crm_read_workspace_secrets(c.workspace_id)',
    'public.crm_strip_login_identifier_secrets',
)

missing = [x for x in required_unlock if x not in unlock]
missing += [x for x in required_legacy_sessions if x not in legacy_sessions]
missing += [x for x in required_hardening if x not in hardening]
missing += [x for x in required_reauth_bridge if x not in reauth_bridge]
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

# The credential re-auth bridge must not refresh or extend the CRM session, alter
# unlock duration, relax reveal throttles, or reopen any database EXECUTE surface.
for forbidden in (
    'update public.crm_sessions',
    'insert into public.crm_sessions',
    'delete from public.crm_sessions',
    'set created_at',
    'set expires_at',
    "interval '30 days'",
    'grant execute',
    'revoke execute',
):
    if forbidden in reauth_bridge:
        raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED unsafe reauth bridge marker: ' + forbidden)
if reauth_bridge.count('create or replace function') != 1:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED reauth bridge must replace exactly one function')
if "interval '10 minutes'" in reauth_bridge:
    raise SystemExit('SESSION_SECURITY_MIGRATIONS_TESTS_FAILED reauth bridge must not redefine unlock lifetime')

print('SESSION_SECURITY_MIGRATIONS_TESTS_OK: max_session_age=7d; max_active_sessions=4; credential_unlock=10m-session-bound-reauth; uuid_aggregation=valid')
