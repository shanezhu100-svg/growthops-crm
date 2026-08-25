-- Read-only post-check for the all-public function EXECUTE boundary.
-- Expected after apply: anon=0, authenticated=0, service_role=12, and the
-- historical ensure_rls event-trigger helper remains postgres-owned and active.

with expected(signature) as (
  values
    ('crm_bootstrap_admin(text,text,text,text)'),
    ('crm_client_account_safe_summary(text,text)'),
    ('crm_delete_user(text,uuid)'),
    ('crm_list_users(text)'),
    ('crm_load_state_v3(text)'),
    ('crm_login_v3(text,text)'),
    ('crm_logout(text)'),
    ('crm_public_status()'),
    ('crm_reveal_client_secret_value_v5(text,text,text,text,text,text)'),
    ('crm_save_state(text,jsonb,bigint)'),
    ('crm_unlock_credentials_v1(text,text)'),
    ('crm_upsert_user(text,uuid,text,text,text,text,boolean)')
), public_functions as (
  select p.oid, p.oid::regprocedure::text as signature
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
), service_surface as (
  select pf.signature
  from public_functions pf
  where has_function_privilege('service_role', pf.oid, 'EXECUTE')
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
  select e.evtname, e.evtevent, e.evtenabled::text as enabled, e.evttags, e.evtfoid
  from pg_event_trigger e
  where e.evtname = 'ensure_rls'
)
select
  (select count(*) from public_functions pf where has_function_privilege('anon', pf.oid, 'EXECUTE')) as anon_exec,
  (select count(*) from public_functions pf where has_function_privilege('authenticated', pf.oid, 'EXECUTE')) as authenticated_exec,
  (select count(*) from service_surface) as service_role_exec,
  (select count(*) from service_surface s left join expected e using (signature) where e.signature is null) as unexpected_service_role_exec,
  (select count(*) from expected e left join service_surface s using (signature) where s.signature is null) as missing_expected_service_role_exec,
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
from target t
left join event_binding e on true;

select signature as service_role_signature
from service_surface
order by signature;
