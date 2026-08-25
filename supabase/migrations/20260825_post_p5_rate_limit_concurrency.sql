-- Post-P5: serialize security rate-limit subjects and make rejected unlock/reveal
-- audit outcomes commit successfully through the BFF error-envelope bridge.
--
-- Scope is intentionally limited to crm_login, crm_unlock_credentials_v1 and
-- crm_reveal_client_secret_value_v5. Thresholds, authentication order, Vault
-- scalar reveal semantics and the Post-P5 EXECUTE surface are unchanged.

DO $preflight$
DECLARE
  v_login oid := 'public.crm_login(text,text)'::regprocedure;
  v_unlock oid := 'public.crm_unlock_credentials_v1(text,text)'::regprocedure;
  v_reveal oid := 'public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)'::regprocedure;
BEGIN
  IF md5(pg_get_functiondef(v_login)) <> 'd3af3bfea698eab3b6592da29ef3329a' THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_LOGIN_DRIFT:%', md5(pg_get_functiondef(v_login));
  END IF;
  IF md5(pg_get_functiondef(v_unlock)) <> '0d40dda5b2bc99af44e5c39e5295b513' THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_UNLOCK_DRIFT:%', md5(pg_get_functiondef(v_unlock));
  END IF;
  IF md5(pg_get_functiondef(v_reveal)) <> 'd5825feb1a40aad7d9b65fe6e7491b7d' THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_REVEAL_DRIFT:%', md5(pg_get_functiondef(v_reveal));
  END IF;

  IF has_function_privilege('anon',v_login,'EXECUTE')
     OR has_function_privilege('authenticated',v_login,'EXECUTE')
     OR has_function_privilege('service_role',v_login,'EXECUTE') THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_LOGIN_ACL';
  END IF;
  IF has_function_privilege('anon',v_unlock,'EXECUTE')
     OR has_function_privilege('authenticated',v_unlock,'EXECUTE')
     OR NOT has_function_privilege('service_role',v_unlock,'EXECUTE') THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_UNLOCK_ACL';
  END IF;
  IF has_function_privilege('anon',v_reveal,'EXECUTE')
     OR has_function_privilege('authenticated',v_reveal,'EXECUTE')
     OR NOT has_function_privilege('service_role',v_reveal,'EXECUTE') THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_PREFLIGHT_REVEAL_ACL';
  END IF;
END;
$preflight$;

CREATE OR REPLACE FUNCTION public.crm_login(p_username text, p_password text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
declare
  v_user public.crm_users%rowtype;
  v_workspace uuid;
  v_role text;
  v_token text;
  v_state jsonb;
  v_revision bigint;
  v_username_key text := lower(btrim(coalesce(p_username,'')));
  v_headers jsonb := '{}'::jsonb;
  v_headers_text text;
  v_source_ip text := '';
  v_source_bucket text := '';
  v_pair_failures integer := 0;
  v_source_failures integer := 0;
begin
  v_headers_text := current_setting('request.headers', true);
  if nullif(v_headers_text,'') is not null then
    begin
      v_headers := v_headers_text::jsonb;
    exception when others then
      v_headers := '{}'::jsonb;
    end;
  end if;

  -- Prefer the BFF-generated SHA-256 bucket derived from a platform-trusted
  -- visitor IP. Only the 24-hex bucket reaches CRM audit data; raw IP is not stored.
  v_source_bucket := lower(btrim(coalesce(v_headers->>'x-growthops-source-bucket','')));
  if v_source_bucket !~ '^[0-9a-f]{24}$' then
    v_source_bucket := '';
  end if;

  -- Compatibility fallback for trusted direct server/PostgREST callers.
  if v_source_bucket = '' then
    v_source_ip := btrim(split_part(coalesce(v_headers->>'x-forwarded-for',''), ',', 1));
    if v_source_ip = '' then
      v_source_ip := btrim(coalesce(v_headers->>'cf-connecting-ip',''));
    end if;
    if v_source_ip <> '' then
      v_source_bucket := substr(encode(extensions.digest(convert_to(v_source_ip,'UTF8'),'sha256'),'hex'),1,24);
    end if;
  end if;

  if v_source_bucket <> '' then
    -- Serialize the full count -> credential check -> failure-audit transaction
    -- for one trusted source bucket. Hash collisions only add serialization.
    perform pg_catalog.pg_advisory_xact_lock(90813011, pg_catalog.hashtext(v_source_bucket));

    select count(*) into v_pair_failures from public.crm_server_audit_logs
    where action='LOGIN_FAILURE' and created_at >= now()-interval '10 minutes'
      and detail->>'sourceBucket'=v_source_bucket and detail->>'usernameKey'=v_username_key;
    select count(*) into v_source_failures from public.crm_server_audit_logs
    where action='LOGIN_FAILURE' and created_at >= now()-interval '10 minutes'
      and detail->>'sourceBucket'=v_source_bucket;
    if v_pair_failures >= 12 or v_source_failures >= 50 then
      if not exists (
        select 1 from public.crm_server_audit_logs
        where action='LOGIN_THROTTLED' and created_at >= now()-interval '1 minute'
          and detail->>'sourceBucket'=v_source_bucket
      ) then
        insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
        values(null,null,'LOGIN_THROTTLED',jsonb_build_object('sourceBucket',v_source_bucket,'reason','INVALID_CREDENTIALS'));
      end if;
      return jsonb_build_object('error','INVALID_CREDENTIALS');
    end if;
  end if;

  if octet_length(coalesce(p_password,'')) > 72 then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(null,null,'LOGIN_FAILURE',jsonb_strip_nulls(jsonb_build_object(
      'usernameKey',nullif(v_username_key,''),'sourceBucket',nullif(v_source_bucket,''),'reason','INVALID_CREDENTIALS')));
    return jsonb_build_object('error','INVALID_CREDENTIALS');
  end if;

  select * into v_user from public.crm_users where username_key=v_username_key and enabled limit 1;
  if v_user.id is not null then
    select m.workspace_id,m.role into v_workspace,v_role from public.crm_workspace_members m
    where m.user_id=v_user.id and m.enabled order by m.created_at asc limit 1;
  end if;
  if v_user.id is null or v_user.password_hash <> extensions.crypt(coalesce(p_password,''),v_user.password_hash) then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(v_workspace,v_user.id,'LOGIN_FAILURE',jsonb_strip_nulls(jsonb_build_object(
      'usernameKey',nullif(v_username_key,''),'sourceBucket',nullif(v_source_bucket,''),'reason','INVALID_CREDENTIALS')));
    return jsonb_build_object('error','INVALID_CREDENTIALS');
  end if;
  if v_workspace is null then raise exception 'NO_WORKSPACE_ACCESS' using errcode='P0001'; end if;
  delete from public.crm_sessions where user_id=v_user.id and expires_at<=now();
  v_token:=encode(extensions.gen_random_bytes(32),'hex');
  insert into public.crm_sessions(token_hash,user_id,workspace_id,expires_at)
  values(public.crm_token_hash(v_token),v_user.id,v_workspace,now()+interval '30 days');
  select data,revision into v_state,v_revision from public.crm_workspace_state where workspace_id=v_workspace;
  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(v_workspace,v_user.id,'LOGIN',jsonb_strip_nulls(jsonb_build_object('username',v_user.username,'sourceBucket',nullif(v_source_bucket,''))));
  return jsonb_build_object(
    'token',v_token,'workspaceId',v_workspace,
    'state',public.crm_role_view_state(v_role,coalesce(v_state,'{}'::jsonb)),
    'revision',coalesce(v_revision,0),
    'user',jsonb_build_object('id',v_user.id,'name',v_user.name,'username',v_user.username,'role',v_role,'enabled',v_user.enabled)
  );
end;
$function$;

CREATE OR REPLACE FUNCTION public.crm_unlock_credentials_v1(p_token text, p_password text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'pg_catalog'
AS $function$
declare
  c record;
  v_user public.crm_users%rowtype;
  v_session_hash text := public.crm_token_hash(p_token);
  v_unlock_token text;
  v_unlock_hash text;
  v_expires_at timestamptz;
  v_recent_failures integer := 0;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  select * into v_user
  from public.crm_users u
  where u.id=c.user_id and u.enabled
  limit 1;

  if v_user.id is null then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  -- One ADMIN/user/workspace unlock subject is serialized across count, bcrypt
  -- verification and its failure/success audit write.
  perform pg_catalog.pg_advisory_xact_lock(
    90813012,
    pg_catalog.hashtext(c.workspace_id::text || ':' || c.user_id::text)
  );

  select count(*) into v_recent_failures
  from public.crm_server_audit_logs l
  where l.workspace_id=c.workspace_id
    and l.user_id=c.user_id
    and l.action='CREDENTIAL_UNLOCK_FAILURE'
    and l.created_at >= now() - interval '10 minutes';

  if v_recent_failures >= 5 then
    if not exists (
      select 1 from public.crm_server_audit_logs l
      where l.workspace_id=c.workspace_id
        and l.user_id=c.user_id
        and l.action='CREDENTIAL_UNLOCK_THROTTLED'
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_THROTTLED',jsonb_build_object('reason','TOO_MANY_FAILURES'));
    end if;
    -- Return an error envelope so the audit transaction commits; the BFF maps
    -- this envelope back to the existing HTTP 429 contract.
    return jsonb_build_object('error','CREDENTIAL_UNLOCK_THROTTLED');
  end if;

  if octet_length(coalesce(p_password,'')) > 72 then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_FAILURE',jsonb_build_object('reason','INVALID_PASSWORD'));
    return jsonb_build_object('error','CREDENTIAL_UNLOCK_INVALID');
  end if;

  if v_user.password_hash <> extensions.crypt(coalesce(p_password,''),v_user.password_hash) then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_FAILURE',jsonb_build_object('reason','INVALID_PASSWORD'));
    return jsonb_build_object('error','CREDENTIAL_UNLOCK_INVALID');
  end if;

  delete from public.crm_credential_unlocks
  where expires_at <= now()
     or (session_token_hash=v_session_hash and user_id=c.user_id and workspace_id=c.workspace_id);

  v_unlock_token := encode(extensions.gen_random_bytes(32),'hex');
  v_unlock_hash := public.crm_token_hash(v_unlock_token);
  v_expires_at := now() + interval '10 minutes';

  insert into public.crm_credential_unlocks(
    unlock_hash,session_token_hash,user_id,workspace_id,expires_at
  ) values(
    v_unlock_hash,v_session_hash,c.user_id,c.workspace_id,v_expires_at
  );

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK',jsonb_build_object('expiresInSeconds',600));

  return jsonb_build_object(
    'unlockToken',v_unlock_token,
    'expiresAt',v_expires_at
  );
end;
$function$;

CREATE OR REPLACE FUNCTION public.crm_reveal_client_secret_value_v5(
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
as $function$
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

  -- Serialize the successful-reveal counter and Vault read for one ADMIN subject.
  perform pg_catalog.pg_advisory_xact_lock(
    90813013,
    pg_catalog.hashtext(c.workspace_id::text || ':' || c.user_id::text)
  );

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
    -- Preserve the throttle audit row by returning a safe envelope; the BFF
    -- restores the existing HTTP 429 response contract.
    return jsonb_build_object('error','CREDENTIAL_REVEAL_THROTTLED');
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

  v_tree := null;
  v_client := '{}'::jsonb;
  v_accounts := '[]'::jsonb;
  v_account := null;
  v_platform_login := null;

  if coalesce(btrim(v_value),'') = '' then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('value', v_value);
end;
$function$;

-- Preserve exact Post-P5 EXECUTE boundaries after CREATE OR REPLACE.
REVOKE ALL ON FUNCTION public.crm_login(text,text) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.crm_unlock_credentials_v1(text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.crm_unlock_credentials_v1(text,text) TO service_role;
REVOKE ALL ON FUNCTION public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) TO service_role;

DO $postcheck$
DECLARE
  v_login oid := 'public.crm_login(text,text)'::regprocedure;
  v_unlock oid := 'public.crm_unlock_credentials_v1(text,text)'::regprocedure;
  v_reveal oid := 'public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)'::regprocedure;
  d_login text := pg_get_functiondef(v_login);
  d_unlock text := pg_get_functiondef(v_unlock);
  d_reveal text := pg_get_functiondef(v_reveal);
BEGIN
  IF position('pg_advisory_xact_lock(90813011' in d_login) = 0
     OR position('pg_advisory_xact_lock(' in d_login) > position('select count(*) into v_pair_failures' in d_login) THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_LOGIN_LOCK';
  END IF;
  IF position('90813012' in d_unlock) = 0
     OR position('pg_advisory_xact_lock(' in d_unlock) > position('select count(*) into v_recent_failures' in d_unlock) THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_UNLOCK_LOCK';
  END IF;
  IF position('90813013' in d_reveal) = 0
     OR position('pg_advisory_xact_lock(' in d_reveal) > position('select count(*) into v_recent_5m' in d_reveal) THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_REVEAL_LOCK';
  END IF;

  IF position($needle$return jsonb_build_object('error','CREDENTIAL_UNLOCK_INVALID')$needle$ in d_unlock) = 0
     OR position($needle$return jsonb_build_object('error','CREDENTIAL_UNLOCK_THROTTLED')$needle$ in d_unlock) = 0
     OR position($needle$return jsonb_build_object('error','CREDENTIAL_REVEAL_THROTTLED')$needle$ in d_reveal) = 0 THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_COMMITTABLE_ERRORS';
  END IF;

  IF d_login !~ 'v_pair_failures >= 12 or v_source_failures >= 50'
     OR d_unlock !~ 'v_recent_failures >= 5'
     OR d_reveal !~ 'v_recent_5m >= 10 or v_recent_1h >= 40' THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_THRESHOLD_DRIFT';
  END IF;

  IF NOT (SELECT prosecdef FROM pg_proc WHERE oid=v_login)
     OR NOT (SELECT prosecdef FROM pg_proc WHERE oid=v_unlock)
     OR NOT (SELECT prosecdef FROM pg_proc WHERE oid=v_reveal) THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_SECURITY_DEFINER';
  END IF;

  IF (SELECT proconfig FROM pg_proc WHERE oid=v_login) IS DISTINCT FROM ARRAY['search_path=public, extensions']::text[]
     OR (SELECT proconfig FROM pg_proc WHERE oid=v_unlock) IS DISTINCT FROM ARRAY['search_path=public, extensions, pg_catalog']::text[]
     OR (SELECT proconfig FROM pg_proc WHERE oid=v_reveal) IS DISTINCT FROM ARRAY['search_path=public, pg_catalog']::text[] THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_SEARCH_PATH';
  END IF;

  IF has_function_privilege('anon',v_login,'EXECUTE')
     OR has_function_privilege('authenticated',v_login,'EXECUTE')
     OR has_function_privilege('service_role',v_login,'EXECUTE')
     OR has_function_privilege('anon',v_unlock,'EXECUTE')
     OR has_function_privilege('authenticated',v_unlock,'EXECUTE')
     OR NOT has_function_privilege('service_role',v_unlock,'EXECUTE')
     OR has_function_privilege('anon',v_reveal,'EXECUTE')
     OR has_function_privilege('authenticated',v_reveal,'EXECUTE')
     OR NOT has_function_privilege('service_role',v_reveal,'EXECUTE') THEN
    RAISE EXCEPTION 'RATE_LIMIT_CONCURRENCY_POSTCHECK_ACL';
  END IF;
END;
$postcheck$;
