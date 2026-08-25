-- Transactional Production acceptance probe for future public-object defaults.
-- This file intentionally creates temporary-named public objects inside one transaction,
-- asserts their effective ACLs for every application role, rolls everything back,
-- then proves no probe objects remain.

begin;

create table public.growthops_public_acl_probe_table_20260824 (
  id bigint primary key
);

create sequence public.growthops_public_acl_probe_sequence_20260824;

create function public.growthops_public_acl_probe_function_20260824()
returns integer
language sql
as $$ select 1 $$;

select
  has_function_privilege('anon', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE') as fn_anon_execute,
  has_function_privilege('authenticated', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE') as fn_authenticated_execute,
  has_function_privilege('service_role', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE') as fn_service_role_execute,
  exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) x
    where n.nspname = 'public'
      and p.proname = 'growthops_public_acl_probe_function_20260824'
      and pg_get_function_identity_arguments(p.oid) = ''
      and x.grantee = 0
      and x.privilege_type = 'EXECUTE'
  ) as fn_public_execute;

with roles(role_name) as (
  values ('anon'::text), ('authenticated'::text), ('service_role'::text)
)
select
  role_name,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'SELECT') as table_select,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'INSERT') as table_insert,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'UPDATE') as table_update,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'DELETE') as table_delete,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'TRUNCATE') as table_truncate,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'REFERENCES') as table_references,
  has_table_privilege(role_name, 'public.growthops_public_acl_probe_table_20260824', 'TRIGGER') as table_trigger
from roles
order by role_name;

with roles(role_name) as (
  values ('anon'::text), ('authenticated'::text), ('service_role'::text)
)
select
  role_name,
  has_sequence_privilege(role_name, 'public.growthops_public_acl_probe_sequence_20260824', 'USAGE') as sequence_usage,
  has_sequence_privilege(role_name, 'public.growthops_public_acl_probe_sequence_20260824', 'SELECT') as sequence_select,
  has_sequence_privilege(role_name, 'public.growthops_public_acl_probe_sequence_20260824', 'UPDATE') as sequence_update
from roles
order by role_name;

do $probe$
declare
  v_role text;
begin
  if has_function_privilege('anon', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE')
     or has_function_privilege('service_role', 'public.growthops_public_acl_probe_function_20260824()', 'EXECUTE') then
    raise exception 'future non-CRM public function remains executable by an application role';
  end if;

  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) x
    where n.nspname = 'public'
      and p.proname = 'growthops_public_acl_probe_function_20260824'
      and pg_get_function_identity_arguments(p.oid) = ''
      and x.grantee = 0
      and x.privilege_type = 'EXECUTE'
  ) then
    raise exception 'future non-CRM public function retains PUBLIC EXECUTE';
  end if;

  for v_role in
    select unnest(array['anon','authenticated','service_role']::text[])
  loop
    if has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'SELECT')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'INSERT')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'UPDATE')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'DELETE')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'TRUNCATE')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'REFERENCES')
       or has_table_privilege(v_role, 'public.growthops_public_acl_probe_table_20260824', 'TRIGGER') then
      raise exception 'future public table retains application-role privilege for %', v_role;
    end if;

    if has_sequence_privilege(v_role, 'public.growthops_public_acl_probe_sequence_20260824', 'USAGE')
       or has_sequence_privilege(v_role, 'public.growthops_public_acl_probe_sequence_20260824', 'SELECT')
       or has_sequence_privilege(v_role, 'public.growthops_public_acl_probe_sequence_20260824', 'UPDATE') then
      raise exception 'future public sequence retains application-role privilege for %', v_role;
    end if;
  end loop;
end;
$probe$;

rollback;

select
  to_regclass('public.growthops_public_acl_probe_table_20260824') is null as table_rolled_back,
  to_regclass('public.growthops_public_acl_probe_sequence_20260824') is null as sequence_rolled_back,
  to_regprocedure('public.growthops_public_acl_probe_function_20260824()') is null as function_rolled_back;
