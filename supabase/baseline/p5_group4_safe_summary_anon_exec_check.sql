-- Read-only post-change verification for P5 Group 4.
with functions as (
  select p.oid,
         p.proname,
         pg_get_function_identity_arguments(p.oid) as identity_args,
         has_function_privilege('anon',p.oid,'EXECUTE') as anon_exec,
         has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_exec,
         has_function_privilege('service_role',p.oid,'EXECUTE') as service_exec
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'
), target as (
  select * from functions
  where proname='crm_client_account_safe_summary'
    and identity_args='p_token text, p_client_id text'
)
select
  proname,
  identity_args,
  anon_exec,
  authenticated_exec,
  service_exec,
  (select count(*) from target)::int as target_count,
  (select count(*) from functions where anon_exec)::int as total_anon_crm_exec,
  (select count(*) from functions where authenticated_exec)::int as total_authenticated_crm_exec,
  (select count(*) from functions where service_exec)::int as total_service_crm_exec,
  (select count(*) from functions)::int as total_crm_functions
from target;
