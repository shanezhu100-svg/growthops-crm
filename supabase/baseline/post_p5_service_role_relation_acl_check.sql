-- READ ONLY: post-check for service_role direct CRM relation ACL removal.
with crm_tables as (
  select c.oid,c.relname,c.relrowsecurity
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')
), crm_functions as (
  select p.oid
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'
)
select
  (select count(*) from crm_tables)::int crm_tables,
  (select count(*) from crm_tables where relrowsecurity)::int rls_enabled,
  (select count(*) from crm_functions)::int crm_functions,
  (select count(*) from crm_functions where has_function_privilege('anon',oid,'EXECUTE'))::int anon_rpc_exec,
  (select count(*) from crm_functions where has_function_privilege('authenticated',oid,'EXECUTE'))::int authenticated_rpc_exec,
  (select count(*) from crm_functions where has_function_privilege('service_role',oid,'EXECUTE'))::int service_rpc_exec,
  (select count(*) from information_schema.role_table_grants where table_schema='public' and table_name like 'crm_%' and grantee='service_role')::int service_table_grant_rows,
  (has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','USAGE')) service_sequence_any,
  (has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','USAGE')) anon_sequence_any,
  (has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','USAGE')) authenticated_sequence_any,
  (select version||' / '||name from supabase_migrations.schema_migrations order by version desc limit 1) latest_migration;
