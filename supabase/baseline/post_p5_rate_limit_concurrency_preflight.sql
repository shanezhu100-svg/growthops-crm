-- Read-only preflight for Post-P5 rate-limit concurrency hardening.
select
  p.proname,
  pg_get_function_identity_arguments(p.oid) as identity_args,
  md5(pg_get_functiondef(p.oid)) as definition_md5,
  p.prosecdef as security_definer,
  p.proconfig,
  has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute,
  has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute,
  has_function_privilege('service_role',p.oid,'EXECUTE') as service_role_execute
from pg_proc p
join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public'
  and p.proname in ('crm_login','crm_unlock_credentials_v1','crm_reveal_client_secret_value_v5')
order by p.proname, pg_get_function_identity_arguments(p.oid);

select
  count(*) filter (where action='CREDENTIAL_UNLOCK_FAILURE') as unlock_failure_rows,
  count(*) filter (where action='CREDENTIAL_UNLOCK_THROTTLED') as unlock_throttled_rows,
  count(*) filter (where action='REVEAL_CLIENT_SECRET_FIELD_THROTTLED') as reveal_throttled_rows
from public.crm_server_audit_logs;
