-- GrowthOps CRM supplemental public-schema recovery fingerprint.
--
-- Purpose:
--   Broaden recovery/drift comparison beyond the historical crm_* primary
--   fingerprint and the three-guard supplemental fingerprint without selecting
--   any application/customer table rows or Vault secret values.
--
-- Safety:
--   Read-only catalog inspection only. This query emits only a line count and a
--   SHA-256 digest. It does not emit function definitions, relation data, Vault
--   plaintext, credential material, or a reconstructable schema dump.
--
-- This is comparison evidence, NOT a replacement for an authorized portable
-- schema-only pg_dump / `supabase db dump` artifact.

with inventory(line) as (
  select
    'SCHEMA|public|owner=' || pg_get_userbyid(n.nspowner) ||
    '|acl=' || coalesce(n.nspacl::text, '')
  from pg_namespace n
  where n.nspname = 'public'

  union all

  select
    'REL|' || c.relname ||
    '|kind=' || c.relkind::text ||
    '|owner=' || pg_get_userbyid(c.relowner) ||
    '|persistence=' || c.relpersistence::text ||
    '|rls=' || c.relrowsecurity::text ||
    '|force_rls=' || c.relforcerowsecurity::text ||
    '|acl=' || coalesce(c.relacl::text, '')
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind in ('r', 'p', 'S', 'v', 'm', 'f')

  union all

  select
    'COL|' || table_name || '|' || lpad(ordinal_position::text, 4, '0') ||
    '|' || column_name || '|' || data_type ||
    '|nullable=' || is_nullable ||
    '|default=' || coalesce(column_default, '') ||
    '|identity=' || is_identity || ':' || coalesce(identity_generation, '') ||
    '|generated=' || is_generated || ':' || coalesce(generation_expression, '')
  from information_schema.columns
  where table_schema = 'public'

  union all

  select
    'CON|' || conrelid::regclass::text || '|' || conname || '|' ||
    contype::text || '|' || pg_get_constraintdef(oid, true)
  from pg_constraint
  where connamespace = 'public'::regnamespace

  union all

  select 'IDX|' || tablename || '|' || indexname || '|' || indexdef
  from pg_indexes
  where schemaname = 'public'

  union all

  select
    'TRG|' || c.relname || '|' || t.tgname || '|' ||
    pg_get_triggerdef(t.oid, true)
  from pg_trigger t
  join pg_class c on c.oid = t.tgrelid
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and not t.tgisinternal

  union all

  select
    'FUNC|' || p.proname || '|' || pg_get_function_identity_arguments(p.oid) ||
    '|kind=' || p.prokind::text ||
    '|owner=' || pg_get_userbyid(p.proowner) ||
    '|security_definer=' || p.prosecdef::text ||
    '|leakproof=' || p.proleakproof::text ||
    '|volatility=' || p.provolatile::text ||
    '|parallel=' || p.proparallel::text ||
    '|config=' || coalesce(array_to_string(p.proconfig, ','), '') ||
    '|acl=' || coalesce(p.proacl::text, '') ||
    '|def=' || pg_get_functiondef(p.oid)
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'

  union all

  select
    'FPRIV|' || p.proname || '|' || pg_get_function_identity_arguments(p.oid) ||
    '|anon=' || has_function_privilege('anon', p.oid, 'EXECUTE')::text ||
    '|authenticated=' || has_function_privilege('authenticated', p.oid, 'EXECUTE')::text ||
    '|service_role=' || has_function_privilege('service_role', p.oid, 'EXECUTE')::text
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'

  union all

  select
    'POL|' || schemaname || '|' || tablename || '|' || policyname || '|' ||
    permissive || '|' || roles::text || '|' || cmd || '|' ||
    coalesce(qual, '') || '|' || coalesce(with_check, '')
  from pg_policies
  where schemaname = 'public'

  union all

  select
    'EVT|' || e.evtname || '|' || e.evtevent ||
    '|enabled=' || e.evtenabled::text ||
    '|tags=' || coalesce(array_to_string(e.evttags, ','), '') ||
    '|func=' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')'
  from pg_event_trigger e
  join pg_proc p on p.oid = e.evtfoid
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'

  union all

  select
    'DEFACL|owner=' || pg_get_userbyid(d.defaclrole) ||
    '|schema=' || coalesce(n.nspname, '<global>') ||
    '|type=' || d.defaclobjtype::text ||
    '|acl=' || coalesce(d.defaclacl::text, '')
  from pg_default_acl d
  left join pg_namespace n on n.oid = d.defaclnamespace
  where d.defaclnamespace = 0
     or n.nspname = 'public'

  union all

  select
    'EXT|' || e.extname || '|' || e.extversion ||
    '|schema=' || n.nspname ||
    '|relocatable=' || e.extrelocatable::text
  from pg_extension e
  join pg_namespace n on n.oid = e.extnamespace
)
select
  count(*)::bigint as inventory_lines,
  encode(
    extensions.digest(
      convert_to(string_agg(line, E'\n' order by line), 'UTF8'),
      'sha256'
    ),
    'hex'
  ) as public_recovery_sha256
from inventory;
