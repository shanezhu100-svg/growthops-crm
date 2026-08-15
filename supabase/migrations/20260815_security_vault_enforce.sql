-- Security hotfix stage 2: enforce Vault as the only persistent credential store.
-- Run only after the redacted frontend using crm_login_v3/crm_load_state_v3 is
-- promoted to Production and its Preview/Production checks pass.

create or replace function public.crm_role_view_state(p_role text, p_state jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare s jsonb:=public.crm_redact_secrets(coalesce(p_state,'{}'::jsonb));
begin
  if p_role='FINANCE' then
    s:=s - 'leads' - 'mediaTools' - 'sopProgress' - 'sopProgressStore' - 'backupSnapshots';
  elsif p_role='OPS' then
    s:=s - 'leads'
         - 'financeActualRebates' - 'financeReceivables' - 'financeCosts' - 'financeReconciliations' - 'financeMonthLocks' - 'financeMonthSnapshots'
         - 'backupSnapshots';
  elsif p_role='SALES' then
    s:=s - 'financeActualRebates' - 'financeReceivables' - 'financeCosts' - 'financeReconciliations' - 'financeMonthLocks' - 'financeMonthSnapshots'
         - 'mediaTools' - 'sopProgress' - 'sopProgressStore' - 'backupSnapshots';
  end if;
  return s;
end
$$;

create or replace function public.crm_save_state(
  p_token text,
  p_state jsonb,
  p_expected_revision bigint default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  c record;
  v_current bigint;
  v_next bigint;
  v_old jsonb;
  v_public_old jsonb;
  v_public_incoming jsonb;
  v_public_saved jsonb;
  v_secret_old jsonb;
  v_secret_updates jsonb;
  v_secret_merged jsonb;
  v_secret_pruned jsonb;
begin
  select * into c from public.crm_session_context(p_token);

  select data, revision into v_old, v_current
  from public.crm_workspace_state
  where workspace_id=c.workspace_id
  for update;

  if p_expected_revision is not null and v_current<>p_expected_revision then
    raise exception 'CLOUD_REVISION_CONFLICT:%',v_current using errcode='P0001';
  end if;

  v_public_old := public.crm_redact_secrets(coalesce(v_old,'{}'::jsonb));
  v_public_incoming := public.crm_redact_secrets(coalesce(p_state,'{}'::jsonb));
  v_public_saved := public.crm_restore_role_restricted(c.role, v_public_incoming, v_public_old);

  v_secret_old := public.crm_read_workspace_secrets(c.workspace_id);
  if c.role='ADMIN' then
    v_secret_updates := public.crm_extract_live_secrets(coalesce(p_state,'{}'::jsonb));
    v_secret_merged := public.crm_merge_secret_updates(v_secret_updates, v_secret_old);
  else
    v_secret_merged := v_secret_old;
  end if;

  v_secret_pruned := public.crm_prune_live_secrets(v_public_saved, v_secret_merged);
  perform public.crm_write_workspace_secrets(c.workspace_id, v_secret_pruned, c.user_id);

  v_next:=v_current+1;
  update public.crm_workspace_state
     set data=v_public_saved,
         revision=v_next,
         updated_at=now(),
         updated_by=c.user_id
   where workspace_id=c.workspace_id;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(c.workspace_id,c.user_id,'SAVE_STATE',jsonb_build_object('revision',v_next,'role',c.role));

  return jsonb_build_object('revision',v_next,'updatedAt',now());
end
$$;

update public.crm_workspace_state
set data = public.crm_redact_secrets(coalesce(data,'{}'::jsonb)),
    updated_at = now()
where data <> public.crm_redact_secrets(coalesce(data,'{}'::jsonb));

revoke all on function public.crm_role_view_state(text,jsonb) from public, anon, authenticated;
grant execute on function public.crm_role_view_state(text,jsonb) to service_role;

comment on function public.crm_save_state(text,jsonb,bigint) is
  'Vault-enforced save path: ordinary workspace JSON is always secret-free; ADMIN secret updates are routed to Vault.';
