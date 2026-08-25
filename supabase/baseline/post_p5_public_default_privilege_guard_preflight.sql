-- Read-only Production preflight for future public-object ACL hardening.
-- Expected before migration:
--   * existing public function effective EXECUTE = anon 0 / authenticated 0 / service_role 12;
--   * postgres/public default ACL still grants service_role on tables/sequences/functions;
--   * the new non-CRM function guard is absent.

with default_acl as (
  select
    pg_get_userbyid(d.defaclrole) as owner,
    n.nspname as schema_name,
    d.defaclobjtype,
    coalesce(r.rolname, 'PUBLIC') as grantee,
    x.privilege_type
  from pg_default_acl d
  left join pg_namespace n on n.oid = d.defaclnamespace
  cross join lateral aclexplode(d.defaclacl) x
  left join pg_roles r on r.oid = x.grantee
  where pg_get_userbyid(d.defaclrole) = 'postgres'
    and n.nspname = 'public'
)
select
  'postgres_public_default_acl' as section,
  defaclobjtype,
  grantee,
  string_agg(privilege_type, ',' order by privilege_type) as privileges
from default_acl
where grantee in ('PUBLIC','anon','authenticated','service_role')
group by defaclobjtype, grantee
order by defaclobjtype, grantee;

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
  ) as noncrm_app_executable,
  to_regprocedure('public.growthops_public_noncrm_function_acl_guard_ddl()') is not null as target_guard_present
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.prokind in ('f','p');

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
