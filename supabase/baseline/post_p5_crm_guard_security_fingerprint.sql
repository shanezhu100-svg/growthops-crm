-- GrowthOps CRM Post-P5 guard security fingerprint
-- READ-ONLY. This supplements p0_schema_security_fingerprint.sql without changing
-- its historical/current crm_* catalog hash contract.
--
-- Production checkpoint on 2026-08-24 after post_p5_user_identity_byte_caps:
--   guard_inventory_lines = 6
--   guard_security_sha256 = d3491022f0827324c810d401123d6027c0c3d46498868a2b5520bbea54bae52f
--
-- Scope: repository-managed GrowthOps CRM ACL/RLS DDL guard functions, their
-- application-role EXECUTE truth, and the event-trigger bindings themselves.

with guard_inventory as (
  select 'GFUNC|' || p.proname || '|' || pg_get_function_identity_arguments(p.oid) ||
         '|owner=' || pg_get_userbyid(p.proowner) ||
         '|def=' || pg_get_functiondef(p.oid) as line
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname='public'
    and p.proname in ('growthops_crm_acl_guard_ddl','growthops_crm_rls_guard_ddl')

  union all

  select 'GPRIV|' || p.proname || '|' || pg_get_function_identity_arguments(p.oid) ||
         '|anon=' || has_function_privilege('anon',p.oid,'EXECUTE')::text ||
         '|authenticated=' || has_function_privilege('authenticated',p.oid,'EXECUTE')::text ||
         '|service_role=' || has_function_privilege('service_role',p.oid,'EXECUTE')::text
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname='public'
    and p.proname in ('growthops_crm_acl_guard_ddl','growthops_crm_rls_guard_ddl')

  union all

  select 'GEVT|' || e.evtname || '|' || e.evtevent || '|' || e.evtenabled::text ||
         '|tags=' || coalesce(array_to_string(e.evttags,','),'') ||
         '|func=' || p.proname || '|' || pg_get_function_identity_arguments(p.oid)
  from pg_event_trigger e
  join pg_proc p on p.oid=e.evtfoid
  where e.evtname in ('growthops_crm_acl_guard_ddl','growthops_crm_rls_guard_ddl')
)
select count(*)::bigint as guard_inventory_lines,
       encode(
         extensions.digest(
           convert_to(string_agg(line,E'\n' order by line),'UTF8'),
           'sha256'
         ),
         'hex'
       ) as guard_security_sha256
from guard_inventory;
