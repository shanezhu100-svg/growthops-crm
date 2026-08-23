-- READ-ONLY preflight for the Post-P5 CRM ALTER-table RLS guard.
with f as (
  select p.oid from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'
), tables as (
  select c.oid,c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')
), inventory as (
  select 'COL|'||table_name||'|'||lpad(ordinal_position::text,4,'0')||'|'||column_name||'|'||data_type||'|'||is_nullable||'|'||coalesce(column_default,'') line from information_schema.columns where table_schema='public' and table_name like 'crm_%'
  union all select 'CON|'||conrelid::regclass::text||'|'||conname||'|'||contype::text||'|'||pg_get_constraintdef(oid) from pg_constraint where connamespace='public'::regnamespace and conrelid<>0 and conrelid::regclass::text like 'crm_%'
  union all select 'IDX|'||tablename||'|'||indexname||'|'||indexdef from pg_indexes where schemaname='public' and tablename like 'crm_%'
  union all select 'TRG|'||c.relname||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid,true) from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'crm_%' and not t.tgisinternal
  union all select 'FUNC|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|'||pg_get_functiondef(p.oid) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all select 'FPRIV|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|anon='||has_function_privilege('anon',p.oid,'EXECUTE')::text||'|authenticated='||has_function_privilege('authenticated',p.oid,'EXECUTE')::text||'|service_role='||has_function_privilege('service_role',p.oid,'EXECUTE')::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all select 'TPRIV|'||grantee||'|'||table_name||'|'||privilege_type from information_schema.role_table_grants where table_schema='public' and table_name like 'crm_%' and grantee in ('anon','authenticated','service_role')
  union all select 'RLS|'||c.relname||'|'||c.relrowsecurity::text||'|'||c.relforcerowsecurity::text from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')
  union all select 'POL|'||schemaname||'|'||tablename||'|'||policyname||'|'||cmd||'|'||coalesce(qual,'')||'|'||coalesce(with_check,'') from pg_policies where schemaname='public' and tablename like 'crm_%'
)
select
  (select count(*) from f) crm_functions,
  (select count(*) from f where has_function_privilege('service_role',oid,'EXECUTE')) service_exec,
  (select count(*) from tables) crm_tables,
  (select count(*) from tables where relrowsecurity) rls_enabled,
  exists(select 1 from pg_event_trigger where evtname='growthops_crm_acl_guard_ddl') acl_guard_present,
  exists(select 1 from pg_event_trigger where evtname='ensure_rls') create_rls_guard_present,
  exists(select 1 from pg_event_trigger where evtname='growthops_crm_rls_guard_ddl') alter_rls_guard_present,
  (select version||' / '||name from supabase_migrations.schema_migrations order by version desc limit 1) latest_migration,
  (select count(*) from inventory) inventory_lines,
  (select encode(extensions.digest(convert_to(string_agg(line,E'\n' order by line),'UTF8'),'sha256'),'hex') from inventory) fingerprint;
