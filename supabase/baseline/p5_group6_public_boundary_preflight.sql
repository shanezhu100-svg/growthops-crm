-- GrowthOps CRM P5 Group 6 public-boundary preflight.
-- READ-ONLY inventory. Do not run as a migration.

with f as (
  select p.oid,
         p.proname,
         pg_get_function_identity_arguments(p.oid) as args,
         lower(pg_get_functiondef(p.oid)) as src,
         has_function_privilege('anon',p.oid,'EXECUTE') as anon_exec,
         has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_exec,
         has_function_privilege('service_role',p.oid,'EXECUTE') as service_exec
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
    and p.proname in ('crm_login','crm_login_v3','crm_public_status')
),
checks(test_name,status,observed) as (
  select 'public_boundary_exact_functions',
         case when count(*)=3 then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from f

  union all
  select 'internal_login_service_only',
         case when count(*)=1 and bool_and(not anon_exec and not authenticated_exec and service_exec) then 'PASS' else 'FAIL' end,
         coalesce(max('anon='||anon_exec||'; auth='||authenticated_exec||'; service='||service_exec),'missing')
  from f where proname='crm_login'

  union all
  select 'login_wrapper_current_pre_revoke_shape',
         case when count(*)=1 and bool_and(anon_exec and not authenticated_exec and service_exec) then 'PASS' else 'FAIL' end,
         coalesce(max('anon='||anon_exec||'; auth='||authenticated_exec||'; service='||service_exec),'missing')
  from f where proname='crm_login_v3'

  union all
  select 'public_status_current_pre_revoke_shape',
         case when count(*)=1 and bool_and(anon_exec and not authenticated_exec and service_exec) then 'PASS' else 'FAIL' end,
         coalesce(max('anon='||anon_exec||'; auth='||authenticated_exec||'; service='||service_exec),'missing')
  from f where proname='crm_public_status'

  union all
  select 'login_wrapper_redacts_state',
         case when count(*)=1 and bool_and(src like '%crm_login(p_username, p_password)%'
                                            and src like '%crm_redact_secrets%') then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from f where proname='crm_login_v3'

  union all
  select 'internal_login_password_audit_throttle_session_guards',
         case when count(*)=1 and bool_and(
           src like '%extensions.crypt%'
           and src like '%login_failure%'
           and src like '%login_throttled%'
           and src like '%interval ''10 minutes''%'
           and src like '%v_pair_failures >= 12%'
           and src like '%v_source_failures >= 50%'
           and src like '%extensions.digest%'
           and src like '%gen_random_bytes(32)%'
           and src like '%crm_token_hash%'
           and src like '%crm_role_view_state%'
           and src like '%''login''%'
         ) then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from f where proname='crm_login'

  union all
  select 'public_status_minimal_shape',
         case when count(*)=1 and bool_and(
           src like '%''initialized''%'
           and src like '%''service''%'
           and src like '%growthops crm cloud%'
           and src not like '%password%'
           and src not like '%twofa%'
           and src not like '%token%'
           and src not like '%vault%'
           and src not like '%client%'
           and src not like '%workspace%'
         ) then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from f where proname='crm_public_status'
)
select test_name,status,observed
from checks
order by test_name;
