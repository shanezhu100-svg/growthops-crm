-- Credential reveal re-auth bridge.
--
-- A successful crm_unlock_credentials_v1 call proves the current ADMIN password
-- again and creates a 10-minute unlock bound to the exact CRM session, user, and
-- workspace. Treat that still-valid unlock as a fresh re-auth signal for the
-- field-level reveal path, instead of forcing a second full CRM login solely
-- because the underlying session is older than 12 hours.
--
-- Deliberately unchanged:
-- - CRM session created_at / expires_at / last_seen_at
-- - 7-day session lifetime cap
-- - credential unlock 10-minute lifetime
-- - reveal rate limits
-- - ADMIN-only enforcement
-- - Vault/account scoping
-- - function EXECUTE grants (including P5 Group 1 anon revocation)

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
  v_session_hash text := public.crm_token_hash(p_token);
  v_session_created timestamptz;
  v_has_recent_unlock boolean := false;
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
  where s.token_hash = v_session_hash
    and s.user_id = c.user_id
    and s.workspace_id = c.workspace_id
    and s.expires_at > now()
  limit 1;

  select exists (
    select 1
    from public.crm_credential_unlocks u
    where u.session_token_hash = v_session_hash
      and u.user_id = c.user_id
      and u.workspace_id = c.workspace_id
      and u.expires_at > now()
  ) into v_has_recent_unlock;

  if v_session_created is null
     or (v_session_created < now() - interval '12 hours' and not v_has_recent_unlock) then
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

comment on function public.crm_reveal_client_secret_field_v3(text,text,text,text) is
  'ADMIN field-level Vault reveal. Requires a fresh session or an unexpired password-verified credential unlock bound to the same session/user/workspace; existing field reveal rate limits remain enforced.';
