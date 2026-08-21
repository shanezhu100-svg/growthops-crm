-- Final credential/session hardening.
-- 1) Retire the legacy full-client credential reveal from all browser roles.
-- 2) Enforce a hard 7-day maximum CRM session lifetime at the table boundary.
-- 3) Reduce active sessions per user from 8 to 4 and prune existing excess rows.

-- The browser uses crm_reveal_client_secret_field_v4 (ADMIN + password reauth +
-- session-bound unlock token). The old full-client reveal is server-internal only.
revoke execute on function public.crm_reveal_client_secrets(text,text) from anon, authenticated, public;
grant execute on function public.crm_reveal_client_secrets(text,text) to service_role;

comment on function public.crm_reveal_client_secrets(text,text) is
  'Legacy full-client Vault reveal retained only for privileged server-side compatibility. Browser roles are denied; UI must use crm_reveal_client_secret_field_v4.';

-- Enforce session expiry at the table boundary so a future login/RPC change cannot
-- accidentally create long-lived browser sessions again.
create or replace function public.crm_cap_session_expiry_v2()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  if new.expires_at is null or new.expires_at > now() + interval '7 days' then
    new.expires_at := now() + interval '7 days';
  end if;
  return new;
end
$$;

revoke all on function public.crm_cap_session_expiry_v2() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_cap_session_expiry_v2_trg ON public.crm_sessions;
create trigger crm_cap_session_expiry_v2_trg
before insert or update of expires_at on public.crm_sessions
for each row execute function public.crm_cap_session_expiry_v2();

-- Cap already-issued sessions without forcing all users to log in immediately.
update public.crm_sessions
set expires_at = now() + interval '7 days'
where expires_at > now() + interval '7 days';

-- Keep at most four active sessions per user after every new login.
create or replace function public.crm_limit_active_sessions_per_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_removed integer := 0;
begin
  with ranked as (
    select s.token_hash,
           row_number() over (
             partition by s.user_id
             order by greatest(coalesce(s.last_seen_at,s.created_at),s.created_at) desc,
                      s.created_at desc,
                      s.token_hash desc
           ) as rn
    from public.crm_sessions s
    where s.user_id=new.user_id
      and s.expires_at>now()
  ), deleted as (
    delete from public.crm_sessions s
    using ranked r
    where s.token_hash=r.token_hash
      and r.rn>4
    returning s.token_hash
  )
  select count(*) into v_removed from deleted;

  if v_removed>0 then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(new.workspace_id,new.user_id,'SESSION_PRUNED',jsonb_build_object('removedCount',v_removed,'maxActiveSessions',4));
  end if;

  return new;
end
$$;

revoke all on function public.crm_limit_active_sessions_per_user() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_limit_active_sessions_per_user_trg ON public.crm_sessions;
create trigger crm_limit_active_sessions_per_user_trg
after insert on public.crm_sessions
for each row execute function public.crm_limit_active_sessions_per_user();

-- Apply the four-session limit immediately to existing active sessions and keep
-- only the most recently used sessions. No token values are written to audit logs.
with ranked as (
  select s.token_hash,
         s.user_id,
         s.workspace_id,
         row_number() over (
           partition by s.user_id
           order by greatest(coalesce(s.last_seen_at,s.created_at),s.created_at) desc,
                    s.created_at desc,
                    s.token_hash desc
         ) as rn
  from public.crm_sessions s
  where s.expires_at>now()
), deleted as (
  delete from public.crm_sessions s
  using ranked r
  where s.token_hash=r.token_hash
    and r.rn>4
  returning s.user_id,s.workspace_id
), grouped as (
  select user_id,max(workspace_id::text)::uuid as workspace_id,count(*)::integer as removed_count
  from deleted
  group by user_id
)
insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
select workspace_id,user_id,'SESSION_PRUNED',jsonb_build_object(
  'removedCount',removed_count,
  'maxActiveSessions',4,
  'reason','SECURITY_HARDENING'
)
from grouped;

comment on function public.crm_cap_session_expiry_v2() is
  'Hard table-boundary cap: CRM sessions cannot live longer than 7 days.';
comment on function public.crm_limit_active_sessions_per_user() is
  'Keeps at most 4 recently active, unexpired CRM sessions per user after each new login.';
