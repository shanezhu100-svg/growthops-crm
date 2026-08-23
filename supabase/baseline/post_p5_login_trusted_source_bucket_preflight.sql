-- READ-ONLY preflight for trusted login source-bucket propagation.
with login_fn as (
  select p.oid,p.prosecdef,r.rolname as owner,p.proconfig,pg_get_functiondef(p.oid) as def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  join pg_roles r on r.oid=p.proowner
  where n.nspname='public' and p.proname='crm_login'
    and pg_get_function_identity_arguments(p.oid)='p_username text, p_password text'
), inventory as (
  select 'COL|'||table_name||'|'||lpad(ordinal_position::text,4,'0')||'|'||column_name||'|'||data_type||'|'||is_nullable||'|'||coalesce(column_default,'') as line from information_schema.columns where table_schema='public' and table_name like 'crm_%'
  union all select 'CON|'||conrelid::regclass::text||'|'||conname||'|'||contype::text||'|'||pg_get_constraintdef(oid) from pg_constraint where connamespace='public'::regnamespace and conrelid<>0 and conrelid::regclass::text like 'crm_%'
  union all select 'IDX|'||tablename||'|'||indexname||'|'||indexdef from pg_indexes where schemaname='public' and tablename like 'crm_%'
  union all select 'TRG|'||c.relname||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid,true) from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'crm_%' and not t.tgisinternal
  union all select 'FUNC|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|'||pg_get_functiondef(p.oid) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all select 'FPRIV|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|anon='||has_function_privilege('anon',p.oid,'EXECUTE')::text||'|authenticated='||has_function_privilege('authenticated',p.oid,'EXECUTE')::text||'|service_role='||has_function_privilege('service_role',p.oid,'EXECUTE')::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%'
  union all select 'TPRIV|'||grantee||'|'||table_name||'|'||privilege_type from information_schema.role_table_grants where table_schema='public' and table_name like 'crm_%' and grantee in ('anon','authenticated','service_role')
  union all select 'RLS|'||c.relname||'|'||c.relrowsecurity::text||'|'||c.relforcerowsecurity::text from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'crm_%' and c.relkind in ('r','p')
  union all select 'POL|'||schemaname||'|'||tablename||'|'||policyname||'|'||cmd||'|'||coalesce(qual,'')||'|'||coalesce(with_check,'') from pg_policies where schemaname='public' and tablename like 'crm_%'
), fp as (
  select count(*)::bigint inventory_lines,encode(extensions.digest(convert_to(string_agg(line,E'\n' order by line),'UTF8'),'sha256'),'hex') fingerprint from inventory
)
select
  (select owner from login_fn) as login_owner,
  (select prosecdef from login_fn) as login_security_definer,
  (select proconfig from login_fn) as login_config,
  (select position('x-growthops-source-bucket' in def)>0 from login_fn) as custom_bucket_present,
  (select position('x-forwarded-for' in def)>0 from login_fn) as legacy_xff_present,
  (select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'crm_%') as crm_functions,
  (select count(*) from information_schema.role_table_grants where table_schema='public' and table_name like 'crm_%' and grantee in ('anon','authenticated','service_role')) as crm_direct_table_grants,
  fp.inventory_lines,fp.fingerprint
from fp;
