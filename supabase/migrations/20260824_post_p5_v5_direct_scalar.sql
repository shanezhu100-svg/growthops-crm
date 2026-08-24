-- Post-P5 credential reveal hardening: remove the internal v3 broad-bundle hop.
--
-- The public/BFF contract is unchanged: crm_reveal_client_secret_value_v5 returns
-- only {} or {"value": <one scalar>} for password/twofa. The exact 10-minute
-- unlock token is itself the password re-auth proof, so the v3 fresh-session
-- bridge is redundant on the v5 path. Existing field-v1 rate limits and audit
-- actions are preserved byte-for-byte in meaning so counters do not reset.

create or replace function public.crm_reveal_client_secret_value_v5(
  p_token text,
  p_unlock_token text,
  p_client_id text,
  p_platform text,
  p_account_id text default null,
  p_field text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  c record;
  v_session_hash text := public.crm_token_hash(p_token);
  v_unlock_hash text := public.crm_token_hash(p_unlock_token);
  v_field text := lower(btrim(coalesce(p_field,'')));
  v_platform text;
  v_account_id text;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
  v_accounts jsonb := '[]'::jsonb;
  v_account jsonb := null;
  v_platform_login jsonb := null;
  v_value text;
  v_recent_5m integer := 0;
  v_recent_1h integer := 0;
  v_limit_version text := 'field-v1';
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  if v_field not in ('password','twofa') then
    raise exception 'INVALID_CREDENTIAL_FIELD' using errcode='P0001';
  end if;

  -- Preserve the existing v5 error order: exact unlock is checked before the
  -- platform is validated. A valid unlock is bound to this exact live session,
  -- user and workspace and expires after 10 minutes.
  if not exists (
    select 1
    from public.crm_credential_unlocks u
    where u.unlock_hash = v_unlock_hash
      and u.session_token_hash = v_session_hash
      and u.user_id = c.user_id
      and u.workspace_id = c.workspace_id
      and u.expires_at > now()
  ) then
    raise exception 'CREDENTIAL_UNLOCK_REQUIRED' using errcode='P0001';
  end if;

  v_platform := lower(btrim(coalesce(p_platform,'')));
  v_account_id := btrim(coalesce(p_account_id,''));
  if v_platform not in ('facebook','tiktok','google','instagram') then
    raise exception 'INVALID_CREDENTIAL_PLATFORM' using errcode='P0001';
  end if;

  -- Preserve v3's field-v1 rate-limit namespace so migration cannot reset an
  -- attacker's current window. Successful empty-value reveals count as before.
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

  -- Vault currently stores one encrypted secret tree per workspace, so the Vault
  -- document must be decrypted once. Unlike v3, this function does not construct
  -- or return a client/platform credential bundle after that read.
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
    if v_field='password' and public.crm_secret_value_nonempty(v_client->'fbLoginPassword') then
      v_platform_login := v_client->'fbLoginPassword';
    end if;
    v_accounts := case when jsonb_typeof(v_client->'fbAccounts')='array' then v_client->'fbAccounts' else '[]'::jsonb end;
  elsif v_platform='tiktok' then
    if v_field='password' and public.crm_secret_value_nonempty(v_client->'tkLoginPassword') then
      v_platform_login := v_client->'tkLoginPassword';
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
    -- Keep the previous login-identifier exclusion semantics but search only the
    -- selected account for the requested scalar; no accountSecrets bundle exists.
    v_value := public.crm_secret_value_text_v5(
      public.crm_strip_login_identifier_secrets(v_account),
      v_field
    );
  end if;

  if v_field='password'
     and coalesce(btrim(v_value),'')=''
     and public.crm_secret_value_nonempty(v_platform_login) then
    if jsonb_typeof(v_platform_login)='string' then
      v_value := v_platform_login #>> '{}';
    else
      v_value := v_platform_login::text;
    end if;
  end if;

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

  -- Shorten the lifetime of non-returned plaintext references before serialization.
  v_tree := null;
  v_client := '{}'::jsonb;
  v_accounts := '[]'::jsonb;
  v_account := null;
  v_platform_login := null;

  if coalesce(btrim(v_value),'') = '' then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('value', v_value);
end
$$;

-- Preserve the Post-P5 server-only execution boundary explicitly. CREATE OR
-- REPLACE normally retains ACLs, but explicit grants make drift impossible.
revoke all on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)
  from public, anon, authenticated;
grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)
  to service_role;

comment on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) is
  'ADMIN + exact session-bound 10-minute unlock credential reveal. Directly selects one password/twofa scalar from Vault-backed workspace secrets; no v3/v4 credential bundle is constructed or returned.';
