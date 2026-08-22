-- P5 group 1 read-only privilege check.
-- Expected after the migration:
--   sensitive_anon_exec = 0
--   sensitive_authenticated_exec = 0
--   sensitive_service_exec = 2
--   total_anon_crm_exec = 10
-- No function body, table, RLS, policy, Vault, session, or data access occurs.

with f as (
  select p.oid,
         p.proname,
         pg_get_function_identity_arguments(p.oid) as args,
         has_function_privilege('anon', p.oid, 'EXECUTE') as anon_exec,
         has_function_privilege('authenticated', p.oid, 'EXECUTE') as authenticated_exec,
         has_function_privilege('service_role', p.oid, 'EXECUTE') as service_exec
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname like 'crm_%'
), sensitive as (
  select * from f
  where proname in ('crm_unlock_credentials_v1','crm_reveal_client_secret_value_v5')
)
select
  (select count(*) from sensitive where anon_exec) as sensitive_anon_exec,
  (select count(*) from sensitive where authenticated_exec) as sensitive_authenticated_exec,
  (select count(*) from sensitive where service_exec) as sensitive_service_exec,
  (select count(*) from f where anon_exec) as total_anon_crm_exec,
  (select count(*) from f where service_exec) as total_service_crm_exec,
  (select string_agg(proname, ', ' order by proname) from sensitive where anon_exec) as sensitive_anon_names,
  (select string_agg(proname, ', ' order by proname) from sensitive where not service_exec) as sensitive_missing_service_names;
