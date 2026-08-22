-- GrowthOps CRM P3/P4 attack-style regression inventory
-- READ-ONLY. This file must not perform DDL, DML, grants, revokes, or secret reads.
-- It validates the live authorization/security shape before P5 permission changes.

with functions as (
  select p.oid,
         p.proname,
         lower(pg_get_functiondef(p.oid)) as src,
         has_function_privilege('anon',p.oid,'EXECUTE') as anon_exec,
         has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_exec,
         has_function_privilege('service_role',p.oid,'EXECUTE') as service_exec
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'
),
checks(test_name,status,observed) as (
  select 'all_crm_tables_rls_enabled',
         case when count(*)>0 and bool_and(c.relrowsecurity) then 'PASS' else 'FAIL' end,
         format('tables=%s; rls_enabled=%s',count(*),count(*) filter(where c.relrowsecurity))
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')

  union all
  select 'anon_authenticated_direct_table_grants_absent',
         case when count(*)=0 then 'PASS' else 'FAIL' end,
         format('direct_grants=%s',count(*))
  from information_schema.role_table_grants
  where table_schema='public' and table_name like 'crm_%'
    and grantee in ('anon','authenticated')

  union all
  select 'broad_reveal_anon_blocked',
         case when count(*)=3 and bool_and(not anon_exec and not authenticated_exec and service_exec) then 'PASS' else 'FAIL' end,
         string_agg(proname::text||':anon='||anon_exec||',auth='||authenticated_exec||',service='||service_exec, '; ' order by proname)
  from functions
  where proname in ('crm_reveal_client_secret_field_v3','crm_reveal_client_secret_field_v4','crm_reveal_client_secrets')

  union all
  select 'vault_helpers_browser_roles_blocked',
         case when count(*)=2 and bool_and(not anon_exec and not authenticated_exec and service_exec) then 'PASS' else 'FAIL' end,
         string_agg(proname::text||':anon='||anon_exec||',auth='||authenticated_exec||',service='||service_exec, '; ' order by proname)
  from functions
  where proname in ('crm_read_workspace_secrets','crm_write_workspace_secrets')

  union all
  select 'unlock_v1_admin_password_throttle_constraints',
         case when count(*)=1 and bool_and(src like '%c.role <> ''admin''%'
                                            and src like '%extensions.crypt%'
                                            and src like '%credential_unlock_failure%'
                                            and src like '%>= 5%'
                                            and src like '%interval ''10 minutes''%') then 'PASS' else 'FAIL' end,
         coalesce(max('anon='||anon_exec||'; auth='||authenticated_exec||'; service='||service_exec),'missing')
  from functions where proname='crm_unlock_credentials_v1'

  union all
  select 'reveal_v5_admin_unlock_field_binding',
         case when count(*)=1 and bool_and(src like '%c.role <> ''admin''%'
                                            and src like '%v_field not in (''password'',''twofa'')%'
                                            and src like '%crm_credential_unlocks%'
                                            and src like '%session_token_hash = v_session_hash%'
                                            and src like '%u.user_id = c.user_id%'
                                            and src like '%u.workspace_id = c.workspace_id%'
                                            and src like '%u.expires_at > now()%') then 'PASS' else 'FAIL' end,
         coalesce(max('anon='||anon_exec||'; auth='||authenticated_exec||'; service='||service_exec),'missing')
  from functions where proname='crm_reveal_client_secret_value_v5'

  union all
  select 'user_management_session_workspace_guards',
         case when count(*)=4 and bool_and(src like '%crm_session_context%'
                                            and src like '%workspace%'
                                            and src like '%admin%') then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from functions
  where proname in ('crm_list_users','crm_upsert_user','crm_delete_user','crm_client_account_safe_summary')

  union all
  select 'save_state_session_and_secret_guard',
         case when count(*)=1 and bool_and(src like '%crm_session_context%'
                                            and src like '%crm_redact_secrets%'
                                            and src like '%crm_extract_live_secrets%') then 'PASS' else 'FAIL' end,
         format('functions=%s',count(*))
  from functions where proname='crm_save_state'

  union all
  select 'authenticated_crm_execute_absent',
         case when count(*) filter(where authenticated_exec)=0 then 'PASS' else 'FAIL' end,
         format('authenticated_exec=%s; total_crm_functions=%s',count(*) filter(where authenticated_exec),count(*))
  from functions

  union all
  select 'service_role_exec_all_crm_functions',
         case when count(*)>0 and bool_and(service_exec) then 'PASS' else 'FAIL' end,
         format('service_exec=%s; total_crm_functions=%s',count(*) filter(where service_exec),count(*))
  from functions

  union all
  select 'sensitive_anon_surface_pre_p5',
         case
           when array_agg(proname::text order by proname) filter(where anon_exec)
                = array['crm_reveal_client_secret_value_v5','crm_unlock_credentials_v1']::text[] then 'PENDING_P5'
           when count(*) filter(where anon_exec)=0 then 'PASS_P5_COMPLETE'
           else 'FAIL'
         end,
         coalesce(string_agg(proname::text, ', ' order by proname) filter(where anon_exec),'none')
  from functions
  where proname in ('crm_unlock_credentials_v1','crm_reveal_client_secret_value_v5')
)
select test_name,status,observed
from checks
order by test_name;
