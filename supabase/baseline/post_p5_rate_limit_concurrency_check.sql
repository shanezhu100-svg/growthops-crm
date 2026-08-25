-- Read-only post-check for Post-P5 rate-limit concurrency hardening.
with f as (
  select p.oid,p.proname,pg_get_function_identity_arguments(p.oid) as identity_args,
         pg_get_functiondef(p.oid) as def,p.prosecdef,p.proconfig
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
    and p.proname in ('crm_login','crm_unlock_credentials_v1','crm_reveal_client_secret_value_v5')
)
select
  proname,
  identity_args,
  prosecdef as security_definer,
  proconfig,
  regexp_count(def,'pg_advisory_xact_lock','i') as transaction_lock_calls,
  position('90813011' in def)>0 as login_lock_namespace,
  position('90813012' in def)>0 as unlock_lock_namespace,
  position('90813013' in def)>0 as reveal_lock_namespace,
  position("return jsonb_build_object('error','CREDENTIAL_UNLOCK_INVALID')" in def)>0 as unlock_invalid_committable,
  position("return jsonb_build_object('error','CREDENTIAL_UNLOCK_THROTTLED')" in def)>0 as unlock_throttled_committable,
  position("return jsonb_build_object('error','CREDENTIAL_REVEAL_THROTTLED')" in def)>0 as reveal_throttled_committable,
  has_function_privilege('anon',oid,'EXECUTE') as anon_execute,
  has_function_privilege('authenticated',oid,'EXECUTE') as authenticated_execute,
  has_function_privilege('service_role',oid,'EXECUTE') as service_role_execute
from f
order by proname,identity_args;

select
  count(*) filter (where has_function_privilege('anon',p.oid,'EXECUTE')) as anon_exec,
  count(*) filter (where has_function_privilege('authenticated',p.oid,'EXECUTE')) as authenticated_exec,
  count(*) filter (where has_function_privilege('service_role',p.oid,'EXECUTE')) as service_role_exec
from pg_proc p
join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname like 'crm\_%' escape '\' and p.prokind='f';

select
  count(*) as service_role_direct_relation_grants
from information_schema.table_privileges
where table_schema='public' and table_name like 'crm\_%' escape '\' and grantee='service_role';

select
  count(*) as service_role_direct_sequence_grants
from information_schema.usage_privileges
where object_schema='public' and object_name like 'crm\_%' escape '\'
  and object_type='SEQUENCE' and grantee='service_role';
