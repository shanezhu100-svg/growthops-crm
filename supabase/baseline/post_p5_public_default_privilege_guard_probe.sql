-- Transactional Production acceptance probe for future public-object defaults.
-- This file intentionally creates temporary-named public objects inside one transaction,
-- asserts their effective ACLs, rolls everything back, then proves no probe objects remain.

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

select
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'SELECT') as table_service_select,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'INSERT') as table_service_insert,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'UPDATE') as table_service_update,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'DELETE') as table_service_delete,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'TRUNCATE') as table_service_truncate,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'REFERENCES') as table_service_references,
  has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'TRIGGER') as table_service_trigger;

select
  has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'USAGE') as sequence_service_usage,
  has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'SELECT') as sequence_service_select,
  has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'UPDATE') as sequence_service_update;

do $probe$
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

  if has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'SELECT')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'INSERT')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'UPDATE')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'DELETE')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'TRUNCATE')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'REFERENCES')
     or has_table_privilege('service_role', 'public.growthops_public_acl_probe_table_20260824', 'TRIGGER') then
    raise exception 'future public table retains service_role privilege';
  end if;

  if has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'USAGE')
     or has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'SELECT')
     or has_sequence_privilege('service_role', 'public.growthops_public_acl_probe_sequence_20260824', 'UPDATE') then
    raise exception 'future public sequence retains service_role privilege';
  end if;
end;
$probe$;

rollback;

select
  to_regclass('public.growthops_public_acl_probe_table_20260824') is null as table_rolled_back,
  to_regclass('public.growthops_public_acl_probe_sequence_20260824') is null as sequence_rolled_back,
  to_regprocedure('public.growthops_public_acl_probe_function_20260824()') is null as function_rolled_back;
