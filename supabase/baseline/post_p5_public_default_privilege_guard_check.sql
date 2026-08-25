-- Read-only post-check for future public-object ACL hardening.
-- Target after migration:
--   * postgres/public defaults grant no service_role privileges on tables/sequences/functions;
--   * existing effective public function EXECUTE remains anon 0 / authenticated 0 / service_role 12;
--   * all existing non-CRM public functions/procedures remain app-role denied;
--   * the new non-CRM guard is SECURITY DEFINER, pg_catalog-pinned, externally non-executable,
--     enabled, and bound only to CREATE/ALTER FUNCTION/PROCEDURE.

with default_acl as (
  select
    d.defaclobjtype,
    coalesce(r.rolname, 'PUBLIC') as grantee,
    x.privilege_type
  from pg_default_acl d
  join pg_namespace n on n.oid = d.defaclnamespace
  cross join lateral aclexplode(d.defaclacl) x
  left join pg_roles r on r.oid = x.grantee
  where pg_get_userbyid(d.defaclrole) = 'postgres'
    and n.nspname = 'public'
)
select
  count(*) filter (where defaclobjtype = 'r' and grantee = 'service_role') as table_default_service_role_grants,
  count(*) filter (where defaclobjtype = 'S' and grantee = 'service_role') as sequence_default_service_role_grants,
  count(*) filter (where defaclobjtype = 'f' and grantee = 'service_role') as function_default_service_role_grants
from default_acl;

select
  count(*) filter (where has_function_privilege('anon', p.oid, 'EXECUTE')) as anon_exec,
  count(*) filter (where has_function_privilege('authenticated', p.oid, 'EXECUTE')) as authenticated_exec,
  count(*) filter (where has_function_privilege('service_role', p.oid, 'EXECUTE')) as service_role_exec
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.prokind in ('f','p');

select
  count(*) filter (
    where p.proname !~ '^crm_'
      and (
        has_function_privilege('anon', p.oid, 'EXECUTE')
        or has_function_privilege('authenticated', p.oid, 'EXECUTE')
        or has_function_privilege('service_role', p.oid, 'EXECUTE')
      )
  ) as noncrm_app_executable
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.prokind in ('f','p');

select
  p.proname,
  pg_get_userbyid(p.proowner) as owner,
  p.prosecdef as security_definer,
  p.proconfig,
  pg_get_function_result(p.oid) as function_result,
  has_function_privilege('postgres', p.oid, 'EXECUTE') as postgres_execute,
  has_function_privilege('anon', p.oid, 'EXECUTE') as anon_execute,
  has_function_privilege('authenticated', p.oid, 'EXECUTE') as authenticated_execute,
  has_function_privilege('service_role', p.oid, 'EXECUTE') as service_role_execute
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'growthops_public_noncrm_function_acl_guard_ddl'
  and pg_get_function_identity_arguments(p.oid) = '';

select
  e.evtname,
  e.evtenabled::text as enabled,
  e.evtevent,
  e.evttags,
  p.proname as bound_function,
  n.nspname as bound_schema
from pg_event_trigger e
join pg_proc p on p.oid = e.evtfoid
join pg_namespace n on n.oid = p.pronamespace
where e.evtname = 'growthops_public_noncrm_function_acl_guard_ddl';

select
  count(*) as service_role_direct_relation_grants
from information_schema.table_privileges
where table_schema = 'public'
  and table_name like 'crm\_%' escape '\'
  and grantee = 'service_role';

select
  count(*) as service_role_direct_sequence_grants
from information_schema.usage_privileges
where object_schema = 'public'
  and object_name like 'crm\_%' escape '\'
  and object_type = 'SEQUENCE'
  and grantee = 'service_role';
