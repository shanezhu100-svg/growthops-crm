-- GrowthOps CRM P5 Group 2 post-change privilege check
-- READ-ONLY. Expected after Group 2: target anon=false, authenticated=false,
-- service_role=true; total anon CRM EXECUTE=9; total service_role CRM EXECUTE=40.

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
  where proname='crm_client_credential_status'
    and identity_args='p_token text, p_client_id text'
)
select
  (select count(*) from target) as target_count,
  (select anon_exec from target limit 1) as target_anon_exec,
  (select authenticated_exec from target limit 1) as target_authenticated_exec,
  (select service_exec from target limit 1) as target_service_exec,
  count(*) filter(where anon_exec)::int as total_anon_crm_exec,
  count(*) filter(where authenticated_exec)::int as total_authenticated_crm_exec,
  count(*) filter(where service_exec)::int as total_service_crm_exec,
  count(*)::int as total_crm_functions
from functions;
