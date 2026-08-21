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
      and r.rn>8
    returning s.token_hash
  )
  select count(*) into v_removed from deleted;

  if v_removed>0 then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(new.workspace_id,new.user_id,'SESSION_PRUNED',jsonb_build_object('removedCount',v_removed,'maxActiveSessions',8));
  end if;

  return new;
end
$$;

revoke all on function public.crm_limit_active_sessions_per_user() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_limit_active_sessions_per_user_trg ON public.crm_sessions;
create trigger crm_limit_active_sessions_per_user_trg
after insert on public.crm_sessions
for each row execute function public.crm_limit_active_sessions_per_user();

comment on function public.crm_limit_active_sessions_per_user() is
  'Keeps at most 8 recently active, unexpired CRM sessions per user after each new login; older sessions are revoked and only the removal count is audited.';
