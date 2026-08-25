-- Read-only preflight for the all-public function EXECUTE boundary.
-- Expected before apply: browser roles 0, service_role 13, with the only
-- non-CRM service-role entry being public.rls_auto_enable().

with public_functions as (
  select p.oid, p.proname, p.prosecdef, p.proowner, p.proconfig
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
), role_counts as (
  select
    count(*) filter (where has_function_privilege('anon', oid, 'EXECUTE')) as anon_exec,
    count(*) filter (where has_function_privilege('authenticated', oid, 'EXECUTE')) as authenticated_exec,
    count(*) filter (where has_function_privilege('service_role', oid, 'EXECUTE')) as service_role_exec
  from public_functions
), target as (
  select
    p.oid,
    p.prosecdef,
    pg_get_userbyid(p.proowner) as owner_name,
    coalesce(array_to_string(p.proconfig, ','), '') as proconfig,
    has_function_privilege('anon', p.oid, 'EXECUTE') as anon_execute,
    has_function_privilege('authenticated', p.oid, 'EXECUTE') as authenticated_execute,
    has_function_privilege('service_role', p.oid, 'EXECUTE') as service_role_execute,
    has_function_privilege('postgres', p.oid, 'EXECUTE') as postgres_execute
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'rls_auto_enable'
    and pg_get_function_identity_arguments(p.oid) = ''
    and pg_get_function_result(p.oid) = 'event_trigger'
), event_binding as (
  select
    e.evtname,
    e.evtevent,
    e.evtenabled::text as enabled,
    e.evttags,
    e.evtfoid
  from pg_event_trigger e
  where e.evtname = 'ensure_rls'
)
select
  rc.anon_exec,
  rc.authenticated_exec,
  rc.service_role_exec,
  t.prosecdef as target_security_definer,
  t.owner_name as target_owner,
  t.proconfig as target_config,
  t.anon_execute as target_anon_execute,
  t.authenticated_execute as target_authenticated_execute,
  t.service_role_execute as target_service_role_execute,
  t.postgres_execute as target_postgres_execute,
  e.evtname,
  e.evtevent,
  e.enabled as event_enabled,
  e.evttags as event_tags,
  (e.evtfoid = t.oid) as event_bound_to_target
from role_counts rc
cross join target t
left join event_binding e on true;

-- Inventory the effective service-role surface so the 13th entry is explicit.
select p.oid::regprocedure::text as service_role_signature
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and has_function_privilege('service_role', p.oid, 'EXECUTE')
order by 1;
