-- Read-only acceptance check for the Post-P5 v5 direct-scalar migration.
do $$
declare
  v_oid oid;
  v_def text;
  v_old_v3 oid := 'public.crm_reveal_client_secret_field_v3(text,text,text,text)'::regprocedure;
  v_old_v4 oid := 'public.crm_reveal_client_secret_field_v4(text,text,text,text,text)'::regprocedure;
begin
  select p.oid, pg_get_functiondef(p.oid)
    into v_oid, v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
    and p.oid='public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)'::regprocedure;

  if v_oid is null then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED v5 missing';
  end if;
  if position('crm_reveal_client_secret_field_v3' in v_def)>0
     or position('crm_reveal_client_secret_field_v4' in v_def)>0
     or position('crm_reveal_client_secrets' in v_def)>0 then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED broader reveal dependency remains';
  end if;
  if position('crm_read_workspace_secrets' in v_def)=0
     or position('crm_strip_login_identifier_secrets' in v_def)=0
     or position('crm_secret_value_text_v5' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED direct scalar path incomplete';
  end if;
  if position('REVEAL_CLIENT_SECRET_FIELD_THROTTLED' in v_def)=0
     or position('v_recent_5m >= 10' in v_def)=0
     or position('v_recent_1h >= 40' in v_def)=0
     or position('field-v1' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED rate-limit parity missing';
  end if;
  if position('REVEAL_CLIENT_SECRET_FIELD' in v_def)=0
     or position('rateLimitVersion' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED audit parity missing';
  end if;
  if position('v_field not in (''password'',''twofa'')' in v_def)=0
     or position('v_platform not in (''facebook'',''tiktok'',''google'',''instagram'')' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED allowlist missing';
  end if;
  if not has_function_privilege('service_role',v_oid,'EXECUTE')
     or has_function_privilege('anon',v_oid,'EXECUTE')
     or has_function_privilege('authenticated',v_oid,'EXECUTE') then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED v5 ACL drift';
  end if;
  if has_function_privilege('anon',v_old_v3,'EXECUTE')
     or has_function_privilege('authenticated',v_old_v3,'EXECUTE')
     or has_function_privilege('anon',v_old_v4,'EXECUTE')
     or has_function_privilege('authenticated',v_old_v4,'EXECUTE') then
    raise exception 'V5_DIRECT_SCALAR_CHECK_FAILED old reveal surface reopened';
  end if;
end $$;

select 'POST_P5_V5_DIRECT_SCALAR_OK' as status;
