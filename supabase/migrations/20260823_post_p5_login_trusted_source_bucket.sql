-- Post-P5: restore per-visitor login throttling through the BFF boundary.
-- The BFF derives a 24-hex SHA-256 bucket from a platform-trusted visitor IP
-- and forwards only that bucket to PostgREST. Raw visitor IP is not stored.

create or replace function public.crm_login(p_username text, p_password text)
returns jsonb language plpgsql security definer set search_path to 'public', 'extensions'
as $function$
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
