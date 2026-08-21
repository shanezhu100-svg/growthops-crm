-- GrowthOps CRM P0 schema/security fingerprint
-- READ-ONLY. The output should be compared with the frozen P0 baseline before
-- and after each Cloudflare migration phase.
--
-- P0 checkpoint on 2026-08-21:
--   inventory_lines = 258
--   crm_schema_security_sha256 = d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729

with inventory as (
  select 'COL|'||table_name||'|'||lpad(ordinal_position::text,4,'0')||'|'||
         column_name||'|'||data_type||'|'||is_nullable||'|'||coalesce(column_default,'') as line
  from information_schema.columns
  where table_schema='public' and table_name like 'crm_%'

  union all

  select 'CON|'||conrelid::regclass::text||'|'||conname||'|'||contype::text||'|'||
         pg_get_constraintdef(oid)
  from pg_constraint
  where connamespace='public'::regnamespace
    and conrelid<>0
    and conrelid::regclass::text like 'crm_%'

  union all

  select 'IDX|'||tablename||'|'||indexname||'|'||indexdef
  from pg_indexes
  where schemaname='public' and tablename like 'crm_%'

  union all

  select 'TRG|'||c.relname||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid,true)
  from pg_trigger t
  join pg_class c on c.oid=t.tgrelid
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname like 'crm_%'
    and not t.tgisinternal

  union all

  select 'FUNC|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||'|'||
         pg_get_functiondef(p.oid)
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'

  union all

  select 'FPRIV|'||p.proname||'|'||pg_get_function_identity_arguments(p.oid)||
         '|anon='||has_function_privilege('anon',p.oid,'EXECUTE')::text||
         '|authenticated='||has_function_privilege('authenticated',p.oid,'EXECUTE')::text||
         '|service_role='||has_function_privilege('service_role',p.oid,'EXECUTE')::text
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname like 'crm_%'

  union all

  select 'TPRIV|'||grantee||'|'||table_name||'|'||privilege_type
  from information_schema.role_table_grants
  where table_schema='public'
    and table_name like 'crm_%'
    and grantee in ('anon','authenticated','service_role')

  union all

  select 'RLS|'||c.relname||'|'||c.relrowsecurity::text||'|'||c.relforcerowsecurity::text
  from pg_class c
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname like 'crm_%'
    and c.relkind in ('r','p')

  union all

  select 'POL|'||schemaname||'|'||tablename||'|'||policyname||'|'||cmd||'|'||
         coalesce(qual,'')||'|'||coalesce(with_check,'')
  from pg_policies
  where schemaname='public' and tablename like 'crm_%'
)
select count(*)::bigint as inventory_lines,
       encode(
         extensions.digest(
           convert_to(string_agg(line,E'\n' order by line),'UTF8'),
           'sha256'
         ),
         'hex'
       ) as crm_schema_security_sha256
from inventory;
