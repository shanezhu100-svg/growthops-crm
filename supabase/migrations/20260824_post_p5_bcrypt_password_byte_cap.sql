-- Repository mirror of Production migration 20260824023041 post_p5_bcrypt_password_byte_cap.
-- Prevent pgcrypto bcrypt from silently ignoring password bytes after byte 72.

DO $preflight$
DECLARE
  v_upsert_md5 text;
  v_bootstrap_md5 text;
BEGIN
  SELECT md5(pg_get_functiondef('public.crm_upsert_user(text,uuid,text,text,text,text,boolean)'::regprocedure)) INTO v_upsert_md5;
  SELECT md5(pg_get_functiondef('public.crm_bootstrap_admin(text,text,text,text)'::regprocedure)) INTO v_bootstrap_md5;

  IF v_upsert_md5 <> '48498837112d8cdfa65eb6ecd718d0fe' THEN
    RAISE EXCEPTION 'BCRYPT_CAP_PREFLIGHT_UPSERT_DRIFT:%', v_upsert_md5;
  END IF;
  IF v_bootstrap_md5 <> 'abc401b6479800280b453b7346f57de6' THEN
    RAISE EXCEPTION 'BCRYPT_CAP_PREFLIGHT_BOOTSTRAP_DRIFT:%', v_bootstrap_md5;
  END IF;
END;
$preflight$;

CREATE OR REPLACE FUNCTION public.crm_upsert_user(p_token text, p_user_id uuid, p_name text, p_username text, p_password text, p_role text, p_enabled boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
declare
  c record;
  v_id uuid:=p_user_id;
  v_name text:=btrim(coalesce(p_name,''));
  v_username text:=btrim(coalesce(p_username,''));
  v_admin_count int;
  v_existing_role text;
  v_password_changed boolean:=false;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role<>'ADMIN' then raise exception 'FORBIDDEN' using errcode='P0001'; end if;
  if length(v_name)<1 or length(v_username)<3 then raise exception 'INVALID_USER_FIELDS' using errcode='P0001'; end if;
  if p_role not in ('ADMIN','FINANCE','OPS','SALES') then raise exception 'INVALID_ROLE' using errcode='P0001'; end if;
  if octet_length(coalesce(p_password,''))>72 then raise exception 'PASSWORD_TOO_LONG' using errcode='P0001'; end if;
  if exists(select 1 from public.crm_users where username_key=lower(v_username) and (v_id is null or id<>v_id)) then
    raise exception 'USERNAME_EXISTS' using errcode='P0001';
  end if;

  if v_id is null then
    if length(coalesce(p_password,''))<10 then raise exception 'PASSWORD_TOO_SHORT' using errcode='P0001'; end if;
    insert into public.crm_users(name,username,username_key,password_hash,enabled)
    values(v_name,v_username,lower(v_username),extensions.crypt(p_password,extensions.gen_salt('bf',10)),coalesce(p_enabled,true))
    returning id into v_id;
    insert into public.crm_workspace_members(workspace_id,user_id,role,enabled)
    values(c.workspace_id,v_id,p_role,coalesce(p_enabled,true));
  else
    select role into v_existing_role from public.crm_workspace_members where workspace_id=c.workspace_id and user_id=v_id;
    if v_existing_role is null then raise exception 'USER_NOT_FOUND' using errcode='P0001'; end if;
    if v_id=c.user_id and p_enabled=false then raise exception 'CANNOT_DISABLE_SELF' using errcode='P0001'; end if;

    select count(*) into v_admin_count
    from public.crm_workspace_members m join public.crm_users u on u.id=m.user_id
    where m.workspace_id=c.workspace_id and m.role='ADMIN' and m.enabled and u.enabled;
    if v_existing_role='ADMIN' and (p_role<>'ADMIN' or p_enabled=false) and v_admin_count<=1 then
      raise exception 'LAST_ADMIN' using errcode='P0001';
    end if;

    v_password_changed:=length(coalesce(p_password,''))>=10;
    update public.crm_users set
      name=v_name,
      username=v_username,
      username_key=lower(v_username),
      enabled=coalesce(p_enabled,true),
      updated_at=now(),
      password_hash=case when v_password_changed then extensions.crypt(p_password,extensions.gen_salt('bf',10)) else password_hash end
    where id=v_id;
    update public.crm_workspace_members set role=p_role,enabled=coalesce(p_enabled,true),updated_at=now()
    where workspace_id=c.workspace_id and user_id=v_id;

    if v_password_changed then
      if v_id=c.user_id then
        delete from public.crm_sessions
         where user_id=v_id
           and token_hash<>public.crm_token_hash(p_token);
      else
        delete from public.crm_sessions where user_id=v_id;
      end if;
    end if;
  end if;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(c.workspace_id,c.user_id,'UPSERT_USER',jsonb_build_object('targetUserId',v_id,'role',p_role,'enabled',p_enabled,'passwordChanged',v_password_changed));

  return (select jsonb_build_object('id',u.id,'name',u.name,'username',u.username,'role',m.role,'enabled',(u.enabled and m.enabled))
          from public.crm_users u join public.crm_workspace_members m on m.user_id=u.id and m.workspace_id=c.workspace_id where u.id=v_id);
end;
$function$;

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

REVOKE ALL ON FUNCTION public.crm_upsert_user(text,uuid,text,text,text,text,boolean) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.crm_upsert_user(text,uuid,text,text,text,text,boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) TO service_role;

DO $postcheck$
DECLARE
  v_upsert oid := 'public.crm_upsert_user(text,uuid,text,text,text,text,boolean)'::regprocedure;
  v_bootstrap oid := 'public.crm_bootstrap_admin(text,text,text,text)'::regprocedure;
BEGIN
  IF md5(pg_get_functiondef(v_upsert)) <> '941cd0ecb578b212851d818188e3be40' THEN
    RAISE EXCEPTION 'BCRYPT_CAP_POSTCHECK_UPSERT_FINGERPRINT';
  END IF;
  IF md5(pg_get_functiondef(v_bootstrap)) <> 'ee2d5b74bb2b5fa3ed8e1b4bb214da84' THEN
    RAISE EXCEPTION 'BCRYPT_CAP_POSTCHECK_BOOTSTRAP_FINGERPRINT';
  END IF;
  IF NOT (SELECT prosecdef FROM pg_proc WHERE oid=v_upsert)
     OR NOT (SELECT prosecdef FROM pg_proc WHERE oid=v_bootstrap) THEN
    RAISE EXCEPTION 'BCRYPT_CAP_POSTCHECK_SECURITY_DEFINER';
  END IF;
  IF (SELECT proconfig FROM pg_proc WHERE oid=v_upsert) IS DISTINCT FROM ARRAY['search_path=public, extensions']::text[]
     OR (SELECT proconfig FROM pg_proc WHERE oid=v_bootstrap) IS DISTINCT FROM ARRAY['search_path=public, extensions']::text[] THEN
    RAISE EXCEPTION 'BCRYPT_CAP_POSTCHECK_SEARCH_PATH';
  END IF;
  IF has_function_privilege('anon', v_upsert, 'EXECUTE')
     OR has_function_privilege('authenticated', v_upsert, 'EXECUTE')
     OR has_function_privilege('anon', v_bootstrap, 'EXECUTE')
     OR has_function_privilege('authenticated', v_bootstrap, 'EXECUTE')
     OR NOT has_function_privilege('service_role', v_upsert, 'EXECUTE')
     OR NOT has_function_privilege('service_role', v_bootstrap, 'EXECUTE') THEN
    RAISE EXCEPTION 'BCRYPT_CAP_POSTCHECK_ACL';
  END IF;
END;
$postcheck$;
