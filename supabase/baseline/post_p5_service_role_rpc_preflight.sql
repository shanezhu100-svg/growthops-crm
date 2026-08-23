-- READ-ONLY preflight for post-P5 service_role CRM RPC minimization.
-- Expected accepted baseline before apply:
--   functions=40, PUBLIC/anon/authenticated/service_role=0/0/0/40
--   preserved service_role entries=12, revoke candidates=28
--   RLS=9/9, sequence browser ACL=none
--   migration=20260823104232 / post_p5_revoke_browser_audit_sequence_acl
--   canonical=258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df

with allowed(name) as (values
  ('crm_bootstrap_admin'),
  ('crm_client_account_safe_summary'),
  ('crm_delete_user'),
  ('crm_list_users'),
  ('crm_load_state_v3'),
  ('crm_login_v3'),
  ('crm_logout'),
  ('crm_public_status'),
  ('crm_reveal_client_secret_value_v5'),
  ('crm_save_state'),
  ('crm_unlock_credentials_v1'),
  ('crm_upsert_user')
), funcs as (
  select p.oid,p.proname,
         has_function_privilege('public',p.oid,'EXECUTE') as public_exec,
         has_function_privilege('anon',p.oid,'EXECUTE') as anon_exec,
         has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_exec,
         has_function_privilege('service_role',p.oid,'EXECUTE') as service_exec
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'
), inventory as (
  select 'COL|'||table_name||'|'||lpad(ordinal_position::text,4,'0')||'|'||column_name||'|'||data_type||'|'||is_nullable||'|'||coalesce(column_default,'') as line
  from information_schema.columns where table_schema='public' and table_name like 'crm_%'
  union all
  select 'CON|'||conrelid::regclass::text||'|'||conname||'|'||contype::text||'|'||pg_get_constraintdef(oid)
  from pg_constraint where connamespace='public'::regnamespace and conrelid<>0 and conrelid::regclass::text like 'crm_%'
  union all
  select 'IDX|'||tablename||'|'||indexname||'|'||indexdef from pg_indexes where schemaname='public' and tablename like 'crm_%'
  union all
  select 'TRG|'||c.relname||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid,true)
  from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname like 'crm_%' and not t.tgisinternal
  union all
  select 'FUNC|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|'||pg_get_functiondef(p.oid)
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all
  select 'FPRIV|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|anon='||has_function_privilege('anon',p.oid,'EXECUTE')::text||'|authenticated='||has_function_privilege('authenticated',p.oid,'EXECUTE')::text||'|service_role='||has_function_privilege('service_role',p.oid,'EXECUTE')::text
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all
  select 'TPRIV|'||grantee||'|'||table_name||'|'||privilege_type
  from information_schema.role_table_grants where table_schema='public' and table_name like 'crm_%' and grantee in ('anon','authenticated','service_role')
  union all
  select 'RLS|'||c.relname||'|'||c.relrowsecurity::text||'|'||c.relforcerowsecurity::text
  from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')
  union all
  select 'POL|'||schemaname||'|'||tablename||'|'||policyname||'|'||cmd||'|'||coalesce(qual,'')||'|'||coalesce(with_check,'')
  from pg_policies where schemaname='public' and tablename like 'crm_%'
), fp as (
  select count(*)::bigint as inventory_lines,
         encode(extensions.digest(convert_to(string_agg(line,E'\n' order by line),'UTF8'),'sha256'),'hex') as fingerprint
  from inventory
), tables as (
  select count(*) as crm_tables,count(*) filter (where c.relrowsecurity) as rls_enabled
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relkind='r' and c.relname like 'crm_%'
), migration as (
  select version||' / '||name as latest_migration
  from supabase_migrations.schema_migrations order by version desc limit 1
)
select
  (select count(*) from funcs) as crm_functions,
  (select count(*) from funcs where public_exec) as public_exec,
  (select count(*) from funcs where anon_exec) as anon_exec,
  (select count(*) from funcs where authenticated_exec) as authenticated_exec,
  (select count(*) from funcs where service_exec) as service_exec,
  (select count(*) from funcs f join allowed a on a.name=f.proname where f.service_exec) as preserved_service_exec,
  (select count(*) from funcs f left join allowed a on a.name=f.proname where a.name is null and f.service_exec) as revoke_candidate_service_exec,
  (select array_agg(a.name order by a.name) from allowed a left join funcs f on f.proname=a.name and f.service_exec where f.oid is null) as missing_preserved,
  (select crm_tables from tables) as crm_tables,
  (select rls_enabled from tables) as rls_enabled,
  has_sequence_privilege('public','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('public','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('public','public.crm_server_audit_logs_id_seq','USAGE') as public_any_sequence_priv,
  has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('anon','public.crm_server_audit_logs_id_seq','USAGE') as anon_any_sequence_priv,
  has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','SELECT') or has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','UPDATE') or has_sequence_privilege('authenticated','public.crm_server_audit_logs_id_seq','USAGE') as authenticated_any_sequence_priv,
  has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','SELECT') and has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','UPDATE') and has_sequence_privilege('service_role','public.crm_server_audit_logs_id_seq','USAGE') as service_sequence_all,
  (select latest_migration from migration) as latest_migration,
  (select inventory_lines from fp) as inventory_lines,
  (select fingerprint from fp) as fingerprint;
