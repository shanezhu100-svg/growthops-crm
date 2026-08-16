-- Hard invariant: ordinary CRM workspace JSON must never persist credential keys.
-- Before redacting existing rows, merge any compatibility-era secret fields back
-- into Vault so no credential data is lost.

do $$
declare
  r record;
  v_public jsonb;
  v_secret_old jsonb;
  v_secret_updates jsonb;
  v_secret_merged jsonb;
  v_secret_pruned jsonb;
begin
  for r in
    select workspace_id, data, updated_by
    from public.crm_workspace_state
    for update
  loop
    v_public := public.crm_redact_secrets(coalesce(r.data,'{}'::jsonb));
    v_secret_old := public.crm_read_workspace_secrets(r.workspace_id);
    v_secret_updates := public.crm_extract_live_secrets(coalesce(r.data,'{}'::jsonb));
    v_secret_merged := public.crm_merge_secret_updates(v_secret_updates, v_secret_old);
    v_secret_pruned := public.crm_prune_live_secrets(v_public, v_secret_merged);

    perform public.crm_write_workspace_secrets(
      r.workspace_id,
      v_secret_pruned,
      r.updated_by
    );

    update public.crm_workspace_state
       set data=v_public,
           updated_at=now()
     where workspace_id=r.workspace_id;
  end loop;
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
  v_public_saved := public.crm_redact_secrets(v_public_saved);

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

create or replace function public.crm_workspace_state_secret_guard()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
  new.data := public.crm_redact_secrets(coalesce(new.data,'{}'::jsonb));
  if new.data <> public.crm_redact_secrets(new.data) then
    raise exception 'WORKSPACE_STATE_SECRET_GUARD_FAILED' using errcode='P0001';
  end if;
  return new;
end
$$;

revoke all on function public.crm_workspace_state_secret_guard() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_workspace_state_secret_guard_trg ON public.crm_workspace_state;
create trigger crm_workspace_state_secret_guard_trg
before insert or update of data on public.crm_workspace_state
for each row execute function public.crm_workspace_state_secret_guard();

alter table public.crm_workspace_state
  drop constraint if exists crm_workspace_state_secret_free_chk;
alter table public.crm_workspace_state
  add constraint crm_workspace_state_secret_free_chk
  check (data = public.crm_redact_secrets(data)) not valid;
alter table public.crm_workspace_state
  validate constraint crm_workspace_state_secret_free_chk;

comment on constraint crm_workspace_state_secret_free_chk on public.crm_workspace_state is
  'Hard invariant: ordinary workspace JSON is recursively secret-free; credentials persist only in Vault.';
comment on function public.crm_save_state(text,jsonb,bigint) is
  'Vault-enforced save path. Incoming ADMIN secret updates are merged into Vault; ordinary workspace JSON is always recursively redacted before persistence.';
