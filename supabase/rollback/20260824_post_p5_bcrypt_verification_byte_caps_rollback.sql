-- Exact rollback for Production migration 20260824031938 post_p5_bcrypt_verification_byte_caps.
-- Restores the three pre-migration function definitions and their prior ACL boundary.

DO $preflight$
DECLARE
  v_bootstrap_md5 text;
  v_login_md5 text;
  v_unlock_md5 text;
BEGIN
  SELECT md5(pg_get_functiondef('public.crm_bootstrap_admin(text,text,text,text)'::regprocedure)) INTO v_bootstrap_md5;
  SELECT md5(pg_get_functiondef('public.crm_login(text,text)'::regprocedure)) INTO v_login_md5;
  SELECT md5(pg_get_functiondef('public.crm_unlock_credentials_v1(text,text)'::regprocedure)) INTO v_unlock_md5;

  IF v_bootstrap_md5 <> '108be4243b6cd38522a06da77a2ead7b' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_PREFLIGHT_BOOTSTRAP_DRIFT:%', v_bootstrap_md5;
  END IF;
  IF v_login_md5 <> 'd3af3bfea698eab3b6592da29ef3329a' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_PREFLIGHT_LOGIN_DRIFT:%', v_login_md5;
  END IF;
  IF v_unlock_md5 <> '0d40dda5b2bc99af44e5c39e5295b513' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_PREFLIGHT_UNLOCK_DRIFT:%', v_unlock_md5;
  END IF;
END;
$preflight$;

CREATE OR REPLACE FUNCTION public.crm_bootstrap_admin(p_setup_code text, p_name text, p_username text, p_password text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
declare
  v_workspace uuid;
  v_user uuid;
  v_token text;
  v_username text := btrim(coalesce(p_username,''));
  v_name text := btrim(coalesce(p_name,''));
  v_secret text;
begin
  perform pg_advisory_xact_lock(90813001);
  if exists(select 1 from public.crm_users) then
    raise exception 'ALREADY_INITIALIZED' using errcode='P0001';
  end if;
  select secret_hash into v_secret from public.crm_setup_guard where id=true;
  if v_secret is null or v_secret <> extensions.crypt(coalesce(p_setup_code,''),v_secret) then
    raise exception 'INVALID_SETUP_CODE' using errcode='P0001';
  end if;
  if length(v_name)<1 then raise exception 'NAME_REQUIRED' using errcode='P0001'; end if;
  if length(v_username)<3 then raise exception 'USERNAME_TOO_SHORT' using errcode='P0001'; end if;
  if octet_length(coalesce(p_password,''))>72 then raise exception 'PASSWORD_TOO_LONG' using errcode='P0001'; end if;
  if length(coalesce(p_password,''))<10 then raise exception 'PASSWORD_TOO_SHORT' using errcode='P0001'; end if;

  insert into public.crm_workspaces(name) values('GrowthOps CRM') returning id into v_workspace;
  insert into public.crm_users(name,username,username_key,password_hash)
  values(v_name,v_username,lower(v_username),extensions.crypt(p_password, extensions.gen_salt('bf',10)))
  returning id into v_user;
  insert into public.crm_workspace_members(workspace_id,user_id,role) values(v_workspace,v_user,'ADMIN');
  insert into public.crm_workspace_state(workspace_id,data,revision,updated_by) values(v_workspace,'{}'::jsonb,0,v_user);

  v_token := encode(extensions.gen_random_bytes(32),'hex');
  insert into public.crm_sessions(token_hash,user_id,workspace_id,expires_at)
  values(public.crm_token_hash(v_token),v_user,v_workspace,now()+interval '30 days');
  delete from public.crm_setup_guard where id=true;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(v_workspace,v_user,'BOOTSTRAP_ADMIN',jsonb_build_object('username',v_username));

  return jsonb_build_object(
    'token',v_token,
    'workspaceId',v_workspace,
    'revision',0,
    'state','{}'::jsonb,
    'user',jsonb_build_object('id',v_user,'name',v_name,'username',v_username,'role','ADMIN','enabled',true)
  );
end;
$function$;

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
    raise exception 'CREDENTIAL_UNLOCK_THROTTLED' using errcode='P0001';
  end if;

  if v_user.password_hash <> extensions.crypt(coalesce(p_password,''),v_user.password_hash) then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_FAILURE',jsonb_build_object('reason','INVALID_PASSWORD'));
    raise exception 'CREDENTIAL_UNLOCK_INVALID' using errcode='P0001';
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

REVOKE ALL ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) TO service_role;

REVOKE ALL ON FUNCTION public.crm_login(text,text) FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL ON FUNCTION public.crm_unlock_credentials_v1(text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.crm_unlock_credentials_v1(text,text) TO service_role;

DO $postcheck$
DECLARE
  v_bootstrap oid := 'public.crm_bootstrap_admin(text,text,text,text)'::regprocedure;
  v_login oid := 'public.crm_login(text,text)'::regprocedure;
  v_unlock oid := 'public.crm_unlock_credentials_v1(text,text)'::regprocedure;
BEGIN
  IF md5(pg_get_functiondef(v_bootstrap)) <> 'ee2d5b74bb2b5fa3ed8e1b4bb214da84' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_POSTCHECK_BOOTSTRAP_FINGERPRINT';
  END IF;
  IF md5(pg_get_functiondef(v_login)) <> '88eb27fbc0acb799ef5cb63e35f1168e' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_POSTCHECK_LOGIN_FINGERPRINT';
  END IF;
  IF md5(pg_get_functiondef(v_unlock)) <> '03dbcf1a878ec88b7e9f71ecc9cac5d3' THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_POSTCHECK_UNLOCK_FINGERPRINT';
  END IF;

  IF has_function_privilege('anon', v_bootstrap, 'EXECUTE')
     OR has_function_privilege('authenticated', v_bootstrap, 'EXECUTE')
     OR NOT has_function_privilege('service_role', v_bootstrap, 'EXECUTE')
     OR has_function_privilege('anon', v_login, 'EXECUTE')
     OR has_function_privilege('authenticated', v_login, 'EXECUTE')
     OR has_function_privilege('service_role', v_login, 'EXECUTE')
     OR has_function_privilege('anon', v_unlock, 'EXECUTE')
     OR has_function_privilege('authenticated', v_unlock, 'EXECUTE')
     OR NOT has_function_privilege('service_role', v_unlock, 'EXECUTE') THEN
    RAISE EXCEPTION 'BCRYPT_VERIFY_CAP_ROLLBACK_POSTCHECK_ACL';
  END IF;
END;
$postcheck$;
