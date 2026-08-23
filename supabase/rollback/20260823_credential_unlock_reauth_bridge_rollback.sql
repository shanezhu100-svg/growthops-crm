-- Roll back only the credential unlock -> reveal re-auth bridge.
-- Restores the prior rule: field-level reveal requires the CRM session itself to
-- have been created within the last 12 hours. No EXECUTE grants are changed.

create or replace function public.crm_reveal_client_secret_field_v3(
  p_token text,
  p_client_id text,
  p_platform text,
  p_account_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_catalog
as $$
declare
  c record;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
  v_platform text := lower(btrim(coalesce(p_platform,'')));
  v_account_id text := btrim(coalesce(p_account_id,''));
  v_accounts jsonb := '[]'::jsonb;
  v_account jsonb := null;
  v_result jsonb := '{}'::jsonb;
  v_session_created timestamptz;
  v_recent_5m integer := 0;
  v_recent_1h integer := 0;
  v_limit_version text := 'field-v1';
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  if v_platform not in ('facebook','tiktok','google','instagram') then
    raise exception 'INVALID_CREDENTIAL_PLATFORM' using errcode='P0001';
  end if;

  select s.created_at
    into v_session_created
  from public.crm_sessions s
  where s.token_hash = public.crm_token_hash(p_token)
    and s.user_id = c.user_id
    and s.workspace_id = c.workspace_id
    and s.expires_at > now()
  limit 1;

  if v_session_created is null or v_session_created < now() - interval '12 hours' then
    if not exists (
      select 1
      from public.crm_server_audit_logs l
      where l.user_id = c.user_id
        and l.workspace_id = c.workspace_id
        and l.action = 'REVEAL_CLIENT_SECRET_FIELD_REAUTH_REQUIRED'
        and l.detail->>'rateLimitVersion' = v_limit_version
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(
        c.workspace_id,
        c.user_id,
        'REVEAL_CLIENT_SECRET_FIELD_REAUTH_REQUIRED',
        jsonb_strip_nulls(jsonb_build_object(
          'clientId',coalesce(p_client_id,''),
          'platform',v_platform,
          'accountId',nullif(v_account_id,''),
          'reason','SESSION_NOT_FRESH',
          'rateLimitVersion',v_limit_version
        ))
      );
    end if;
    raise exception 'CREDENTIAL_REAUTH_REQUIRED' using errcode='P0001';
  end if;

  select count(*) into v_recent_5m
  from public.crm_server_audit_logs l
  where l.workspace_id = c.workspace_id
    and l.user_id = c.user_id
    and l.action = 'REVEAL_CLIENT_SECRET_FIELD'
    and l.detail->>'rateLimitVersion' = v_limit_version
    and l.created_at >= now() - interval '5 minutes';

  select count(*) into v_recent_1h
  from public.crm_server_audit_logs l
  where l.workspace_id = c.workspace_id
    and l.user_id = c.user_id
    and l.action = 'REVEAL_CLIENT_SECRET_FIELD'
    and l.detail->>'rateLimitVersion' = v_limit_version
    and l.created_at >= now() - interval '1 hour';

  if v_recent_5m >= 10 or v_recent_1h >= 40 then
    if not exists (
      select 1
      from public.crm_server_audit_logs l
      where l.user_id = c.user_id
        and l.workspace_id = c.workspace_id
        and l.action = 'REVEAL_CLIENT_SECRET_FIELD_THROTTLED'
        and l.detail->>'rateLimitVersion' = v_limit_version
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(
        c.workspace_id,
        c.user_id,
        'REVEAL_CLIENT_SECRET_FIELD_THROTTLED',
        jsonb_strip_nulls(jsonb_build_object(
          'clientId',coalesce(p_client_id,''),
          'platform',v_platform,
          'accountId',nullif(v_account_id,''),
          'window5m',v_recent_5m,
          'window1h',v_recent_1h,
          'rateLimitVersion',v_limit_version
        ))
      );
    end if;
    raise exception 'CREDENTIAL_REVEAL_THROTTLED' using errcode='P0001';
  end if;

  v_tree := public.crm_read_workspace_secrets(c.workspace_id);

  select e.value into v_client
  from jsonb_array_elements(coalesce(v_tree->'clients','[]'::jsonb)) e(value)
  where jsonb_typeof(e.value)='object'
    and e.value->>'id'=coalesce(p_client_id,'')
  limit 1;

  if v_client is null then
    v_client := '{}'::jsonb;
  end if;

  if v_platform='facebook' then
    if public.crm_secret_value_nonempty(v_client->'fbLoginPassword') then
      v_result := v_result || jsonb_build_object('loginPassword',v_client->'fbLoginPassword');
    end if;
    v_accounts := case when jsonb_typeof(v_client->'fbAccounts')='array' then v_client->'fbAccounts' else '[]'::jsonb end;
  elsif v_platform='tiktok' then
    if public.crm_secret_value_nonempty(v_client->'tkLoginPassword') then
      v_result := v_result || jsonb_build_object('loginPassword',v_client->'tkLoginPassword');
    end if;
    v_accounts := case when jsonb_typeof(v_client->'tkAccounts')='array' then v_client->'tkAccounts' else '[]'::jsonb end;
  elsif v_platform='google' then
    v_accounts := case when jsonb_typeof(v_client->'googleAccounts')='array' then v_client->'googleAccounts' else '[]'::jsonb end;
  else
    v_accounts := case when jsonb_typeof(v_client->'instagramAccounts')='array' then v_client->'instagramAccounts' else '[]'::jsonb end;
  end if;

  if jsonb_array_length(v_accounts) > 0 then
    if v_account_id <> '' then
      select e.value into v_account
      from jsonb_array_elements(v_accounts) e(value)
      where jsonb_typeof(e.value)='object'
        and e.value->>'id'=v_account_id
      limit 1;
    elsif jsonb_array_length(v_accounts)=1 then
      v_account := v_accounts->0;
    end if;
  end if;

  if v_account is not null and jsonb_typeof(v_account)='object' then
    v_result := v_result || jsonb_build_object(
      'accountSecrets',
      public.crm_strip_login_identifier_secrets(public.crm_extract_secrets(v_account))
    );
  end if;

  v_result := public.crm_strip_login_identifier_secrets(v_result);

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(
    c.workspace_id,
    c.user_id,
    'REVEAL_CLIENT_SECRET_FIELD',
    jsonb_strip_nulls(jsonb_build_object(
      'clientId',coalesce(p_client_id,''),
      'platform',v_platform,
      'accountId',nullif(v_account_id,''),
      'rateLimitVersion',v_limit_version
    ))
  );

  return coalesce(v_result,'{}'::jsonb);
end
$$;
