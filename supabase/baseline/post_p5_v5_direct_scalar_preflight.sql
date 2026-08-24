-- Read-only preflight for the Post-P5 v5 direct-scalar migration.
do $$
declare
  v_oid oid;
  v_def text;
begin
  select p.oid, pg_get_functiondef(p.oid)
    into v_oid, v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
    and p.oid='public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)'::regprocedure;

  if v_oid is null then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED v5 missing';
  end if;
  if position('crm_reveal_client_secret_field_v3' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED expected current v3 composition not found';
  end if;
  if position('crm_secret_value_text_v5' in v_def)=0 then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED scalar helper missing from current v5';
  end if;
  if not has_function_privilege('service_role',v_oid,'EXECUTE') then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED service_role cannot execute v5';
  end if;
  if has_function_privilege('anon',v_oid,'EXECUTE')
     or has_function_privilege('authenticated',v_oid,'EXECUTE') then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED browser role can execute v5 directly';
  end if;

  if to_regprocedure('public.crm_read_workspace_secrets(uuid)') is null
     or to_regprocedure('public.crm_strip_login_identifier_secrets(jsonb)') is null
     or to_regprocedure('public.crm_secret_value_text_v5(jsonb,text)') is null then
    raise exception 'V5_DIRECT_SCALAR_PREFLIGHT_FAILED dependency missing';
  end if;
end $$;

select 'POST_P5_V5_DIRECT_SCALAR_PREFLIGHT_OK' as status;
