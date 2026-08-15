-- Security hotfix stage 1: move live client/media credentials into Supabase Vault
-- while keeping the legacy ADMIN load path compatible until the new frontend is promoted.
-- Snapshots/audit history are always redacted and are never copied into Vault.

create table if not exists public.crm_workspace_secret_vault (
  workspace_id uuid primary key references public.crm_workspaces(id) on delete cascade,
  vault_secret_id uuid not null unique,
  revision bigint not null default 0,
  updated_at timestamptz not null default now(),
  updated_by uuid null references public.crm_users(id)
);

alter table public.crm_workspace_secret_vault enable row level security;
revoke all on table public.crm_workspace_secret_vault from public, anon, authenticated;
grant select, insert, update, delete on table public.crm_workspace_secret_vault to service_role;

create or replace function public.crm_secret_tree_nonempty(p_value jsonb)
returns boolean
language sql
immutable
set search_path = public, pg_catalog
as $$
  select case jsonb_typeof(p_value)
    when 'object' then p_value <> '{}'::jsonb
    when 'array' then jsonb_array_length(p_value) > 0
    else false
  end
$$;

create or replace function public.crm_secret_value_nonempty(p_value jsonb)
returns boolean
language sql
immutable
set search_path = public, pg_catalog
as $$
  select case jsonb_typeof(p_value)
    when 'string' then length(btrim(p_value #>> '{}')) > 0
    when 'array' then jsonb_array_length(p_value) > 0
    when 'object' then p_value <> '{}'::jsonb
    when 'number' then true
    when 'boolean' then true
    else false
  end
$$;

create or replace function public.crm_extract_secrets(p_value jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare
  k text;
  v jsonb;
  child jsonb;
  item jsonb;
  result jsonb;
begin
  if p_value is null then
    return '{}'::jsonb;
  end if;

  case jsonb_typeof(p_value)
    when 'object' then
      result := '{}'::jsonb;
      for k, v in select * from jsonb_each(p_value) loop
        if public.crm_is_secret_key(k) then
          result := result || jsonb_build_object(k, v);
        elsif k <> 'id' then
          child := public.crm_extract_secrets(v);
          if public.crm_secret_tree_nonempty(child) then
            result := result || jsonb_build_object(k, child);
          end if;
        end if;
      end loop;

      if result <> '{}'::jsonb and p_value ? 'id' then
        result := result || jsonb_build_object('id', p_value->'id');
      end if;
      return result;

    when 'array' then
      result := '[]'::jsonb;
      for item in select value from jsonb_array_elements(p_value) loop
        child := public.crm_extract_secrets(item);
        if public.crm_secret_tree_nonempty(child) then
          result := result || jsonb_build_array(child);
        end if;
      end loop;
      return result;

    else
      return '{}'::jsonb;
  end case;
end
$$;

create or replace function public.crm_extract_live_secrets(p_state jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare
  result jsonb := '{}'::jsonb;
  child jsonb;
begin
  if p_state is null or jsonb_typeof(p_state) <> 'object' then
    return result;
  end if;

  if p_state ? 'clients' then
    child := public.crm_extract_secrets(p_state->'clients');
    if public.crm_secret_tree_nonempty(child) then
      result := result || jsonb_build_object('clients', child);
    end if;
  end if;

  if p_state ? 'mediaTools' then
    child := public.crm_extract_secrets(p_state->'mediaTools');
    if public.crm_secret_tree_nonempty(child) then
      result := result || jsonb_build_object('mediaTools', child);
    end if;
  end if;

  return result;
end
$$;

create or replace function public.crm_merge_secret_updates(p_new jsonb, p_old jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare
  result jsonb;
  k text;
  nv jsonb;
  ov jsonb;
  merged jsonb;
  item jsonb;
  idx int;
  match_idx int;
  item_id text;
begin
  if p_new is null then
    return coalesce(p_old, '{}'::jsonb);
  end if;
  if p_old is null then
    p_old := case jsonb_typeof(p_new) when 'array' then '[]'::jsonb else '{}'::jsonb end;
  end if;

  if jsonb_typeof(p_new) = 'object' then
    result := case when jsonb_typeof(p_old) = 'object' then p_old else '{}'::jsonb end;

    for k, nv in select * from jsonb_each(p_new) loop
      if k = 'id' then
        result := result || jsonb_build_object(k, nv);
      elsif public.crm_is_secret_key(k) then
        if public.crm_secret_value_nonempty(nv) then
          result := result || jsonb_build_object(k, nv);
        end if;
      else
        ov := result->k;
        merged := public.crm_merge_secret_updates(nv, ov);
        if public.crm_secret_tree_nonempty(merged) then
          result := result || jsonb_build_object(k, merged);
        end if;
      end if;
    end loop;

    return result;
  end if;

  if jsonb_typeof(p_new) = 'array' then
    result := case when jsonb_typeof(p_old) = 'array' then p_old else '[]'::jsonb end;
    idx := 0;

    for item in select value from jsonb_array_elements(p_new) loop
      match_idx := null;
      item_id := null;

      if jsonb_typeof(item) = 'object' and item ? 'id' then
        item_id := item->>'id';
        select ordinality::int - 1
          into match_idx
        from jsonb_array_elements(result) with ordinality e(value, ordinality)
        where jsonb_typeof(e.value) = 'object'
          and e.value ? 'id'
          and e.value->>'id' = item_id
        limit 1;
      elsif idx < jsonb_array_length(result) then
        match_idx := idx;
      end if;

      if match_idx is null then
        merged := public.crm_merge_secret_updates(item, null);
        if public.crm_secret_tree_nonempty(merged) then
          result := result || jsonb_build_array(merged);
        end if;
      else
        merged := public.crm_merge_secret_updates(item, result->match_idx);
        result := jsonb_set(result, array[match_idx::text], merged, false);
      end if;

      idx := idx + 1;
    end loop;

    return result;
  end if;

  return coalesce(p_old, '{}'::jsonb);
end
$$;

create or replace function public.crm_read_workspace_secrets(p_workspace_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, vault, pg_catalog
as $$
declare
  v_secret_id uuid;
  v_text text;
begin
  select vault_secret_id into v_secret_id
  from public.crm_workspace_secret_vault
  where workspace_id = p_workspace_id;

  if v_secret_id is null then
    return '{}'::jsonb;
  end if;

  select decrypted_secret into v_text
  from vault.decrypted_secrets
  where id = v_secret_id;

  if v_text is null or btrim(v_text) = '' then
    return '{}'::jsonb;
  end if;

  begin
    return v_text::jsonb;
  exception when others then
    raise exception 'CREDENTIAL_VAULT_CORRUPT' using errcode='P0001';
  end;
end
$$;

create or replace function public.crm_write_workspace_secrets(
  p_workspace_id uuid,
  p_secret_tree jsonb,
  p_user_id uuid default null
)
returns bigint
language plpgsql
security definer
set search_path = public, vault, pg_catalog
as $$
declare
  v_secret_id uuid;
  v_revision bigint;
  v_name text := 'growthops-crm-workspace-' || p_workspace_id::text || '-credentials';
begin
  select vault_secret_id, revision
    into v_secret_id, v_revision
  from public.crm_workspace_secret_vault
  where workspace_id = p_workspace_id
  for update;

  if v_secret_id is null then
    v_secret_id := vault.create_secret(
      coalesce(p_secret_tree, '{}'::jsonb)::text,
      v_name,
      'GrowthOps CRM client/media credentials. Encrypted at rest by Supabase Vault.'
    );

    insert into public.crm_workspace_secret_vault(
      workspace_id, vault_secret_id, revision, updated_at, updated_by
    ) values (
      p_workspace_id, v_secret_id, 1, now(), p_user_id
    );
    return 1;
  end if;

  perform vault.update_secret(
    v_secret_id,
    coalesce(p_secret_tree, '{}'::jsonb)::text,
    v_name,
    'GrowthOps CRM client/media credentials. Encrypted at rest by Supabase Vault.'
  );

  v_revision := coalesce(v_revision, 0) + 1;
  update public.crm_workspace_secret_vault
     set revision = v_revision,
         updated_at = now(),
         updated_by = p_user_id
   where workspace_id = p_workspace_id;

  return v_revision;
end
$$;

create or replace function public.crm_prune_live_secrets(p_public_state jsonb, p_secret_tree jsonb)
returns jsonb
language sql
immutable
set search_path = public, pg_catalog
as $$
  select public.crm_extract_live_secrets(
    public.crm_restore_secrets(
      coalesce(p_public_state, '{}'::jsonb),
      coalesce(p_secret_tree, '{}'::jsonb)
    )
  )
$$;

revoke all on function public.crm_secret_tree_nonempty(jsonb) from public, anon, authenticated;
revoke all on function public.crm_secret_value_nonempty(jsonb) from public, anon, authenticated;
revoke all on function public.crm_extract_secrets(jsonb) from public, anon, authenticated;
revoke all on function public.crm_extract_live_secrets(jsonb) from public, anon, authenticated;
revoke all on function public.crm_merge_secret_updates(jsonb,jsonb) from public, anon, authenticated;
revoke all on function public.crm_read_workspace_secrets(uuid) from public, anon, authenticated;
revoke all on function public.crm_write_workspace_secrets(uuid,jsonb,uuid) from public, anon, authenticated;
revoke all on function public.crm_prune_live_secrets(jsonb,jsonb) from public, anon, authenticated;

do $$
declare
  r record;
  v_secret_tree jsonb;
  v_public jsonb;
  v_compat jsonb;
begin
  for r in
    select workspace_id, data, updated_by
    from public.crm_workspace_state
    for update
  loop
    v_secret_tree := public.crm_extract_live_secrets(coalesce(r.data, '{}'::jsonb));
    perform public.crm_write_workspace_secrets(r.workspace_id, v_secret_tree, r.updated_by);

    v_public := public.crm_redact_secrets(coalesce(r.data, '{}'::jsonb));
    v_compat := public.crm_restore_secrets(v_public, v_secret_tree);

    update public.crm_workspace_state
       set data = v_compat,
           updated_at = now()
     where workspace_id = r.workspace_id;
  end loop;
end
$$;

create or replace function public.crm_role_view_state(p_role text, p_state jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare s jsonb:=coalesce(p_state,'{}'::jsonb);
begin
  if p_role in ('FINANCE','SALES','OPS') then
    s:=public.crm_redact_secrets(s);
  end if;

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
  v_compat_store jsonb;
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

  v_compat_store := public.crm_restore_secrets(v_public_saved, v_secret_pruned);

  v_next:=v_current+1;
  update public.crm_workspace_state
     set data=v_compat_store,
         revision=v_next,
         updated_at=now(),
         updated_by=c.user_id
   where workspace_id=c.workspace_id;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(c.workspace_id,c.user_id,'SAVE_STATE',jsonb_build_object('revision',v_next,'role',c.role));

  return jsonb_build_object('revision',v_next,'updatedAt',now());
end
$$;

create or replace function public.crm_load_state_v3(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  d jsonb;
begin
  d := public.crm_load_state(p_token);
  return jsonb_set(d, '{state}', public.crm_redact_secrets(coalesce(d->'state','{}'::jsonb)), true);
end
$$;

create or replace function public.crm_login_v3(p_username text, p_password text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  d jsonb;
begin
  d := public.crm_login(p_username, p_password);
  if coalesce(d->>'error','') <> '' then
    return d;
  end if;
  return jsonb_set(d, '{state}', public.crm_redact_secrets(coalesce(d->'state','{}'::jsonb)), true);
end
$$;

create or replace function public.crm_reveal_client_secrets(p_token text, p_client_id text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  c record;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  v_tree := public.crm_read_workspace_secrets(c.workspace_id);

  select e.value into v_client
  from jsonb_array_elements(coalesce(v_tree->'clients','[]'::jsonb)) e(value)
  where jsonb_typeof(e.value)='object'
    and e.value->>'id'=coalesce(p_client_id,'')
  limit 1;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(
    c.workspace_id,
    c.user_id,
    'REVEAL_CLIENT_SECRETS',
    jsonb_build_object('clientId',coalesce(p_client_id,''))
  );

  return coalesce(v_client,'{}'::jsonb);
end
$$;

revoke all on function public.crm_load_state_v3(text) from public, anon, authenticated;
revoke all on function public.crm_login_v3(text,text) from public, anon, authenticated;
revoke all on function public.crm_reveal_client_secrets(text,text) from public, anon, authenticated;
grant execute on function public.crm_load_state_v3(text) to anon, authenticated, service_role;
grant execute on function public.crm_login_v3(text,text) to anon, authenticated, service_role;
grant execute on function public.crm_reveal_client_secrets(text,text) to anon, authenticated, service_role;

comment on table public.crm_workspace_secret_vault is
  'Maps each CRM workspace to one Supabase Vault secret containing only live credential fields. No secret values are stored in this table.';
