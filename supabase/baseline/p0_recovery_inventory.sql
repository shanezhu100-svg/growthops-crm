-- GrowthOps CRM Cloudflare migration P0 recovery inventory
-- READ-ONLY: this script must not mutate production data.

-- 1) Live migration ledger.
select version, name
from supabase_migrations.schema_migrations
order by version;

-- 2) CRM business tables / RLS state.
select c.relkind,
       n.nspname as schema_name,
       c.relname as object_name,
       c.relrowsecurity as rls_enabled
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relname like 'crm_%'
  and c.relkind in ('r','p','v','m','S')
order by c.relkind, c.relname;

-- 3) RLS policies. P0 checkpoint currently expects no crm_* policies.
select schemaname, tablename, policyname, roles, cmd
from pg_policies
where schemaname = 'public'
  and tablename like 'crm_%'
order by tablename, policyname;

-- 4) Direct table grants for application-relevant roles.
select grantee,
       table_name,
       string_agg(privilege_type, ',' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema = 'public'
  and table_name like 'crm_%'
  and grantee in ('anon','authenticated','service_role')
group by grantee, table_name
order by table_name, grantee;

-- 5) CRM triggers / security guards.
select event_object_table as table_name,
       trigger_name,
       action_timing,
       event_manipulation
from information_schema.triggers
where trigger_schema = 'public'
  and event_object_table like 'crm_%'
order by event_object_table, trigger_name, event_manipulation;

-- 6) CRM functions and execution privileges.
select p.proname,
       pg_get_function_identity_arguments(p.oid) as args,
       has_function_privilege('anon', p.oid, 'EXECUTE') as anon_exec,
       has_function_privilege('authenticated', p.oid, 'EXECUTE') as auth_exec,
       has_function_privilege('service_role', p.oid, 'EXECUTE') as service_exec
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname like 'crm_%'
order by p.proname, args;

-- 7) Vault row count. Do not select/decrypt secret values.
select count(*)::bigint as vault_secret_rows
from vault.secrets;

-- 8) Sensitive-key scan of ordinary workspace state.
-- P0 checkpoint expects 0.
select count(*)::bigint as workspace_sensitive_key_matches
from public.crm_workspace_state s
cross join lateral jsonb_path_query(s.data, '$.**') as node
cross join lateral jsonb_each(
  case when jsonb_typeof(node) = 'object' then node else '{}'::jsonb end
) as e
where lower(e.key) ~ '(password|passwd|pwd|secret|2fa|two.?factor|otp|totp|recovery.?code|access.?token|refresh.?token|session.?token|api.?key)';

-- 9) Sensitive payload-value scan of server audit details.
-- Boolean metadata such as passwordChanged does not count as a secret payload.
-- P0 checkpoint expects 0.
select count(*)::bigint as audit_sensitive_payload_value_matches
from public.crm_server_audit_logs a
cross join lateral jsonb_path_query(a.detail, '$.**') as node
cross join lateral jsonb_each(
  case when jsonb_typeof(node) = 'object' then node else '{}'::jsonb end
) as e
where lower(e.key) ~ '(password|passwd|pwd|secret|2fa|two.?factor|otp|totp|recovery.?code|access.?token|refresh.?token|session.?token|api.?key)'
  and jsonb_typeof(e.value) in ('string','object','array');

-- 10) Structural inventory useful for recovery comparisons.
select table_name,
       ordinal_position,
       column_name,
       data_type,
       is_nullable,
       coalesce(column_default, '') as column_default
from information_schema.columns
where table_schema = 'public'
  and table_name like 'crm_%'
order by table_name, ordinal_position;

select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and tablename like 'crm_%'
order by tablename, indexname;

select conrelid::regclass::text as table_name,
       conname,
       contype,
       pg_get_constraintdef(oid) as definition
from pg_constraint
where connamespace = 'public'::regnamespace
  and conrelid <> 0
  and conrelid::regclass::text like 'crm_%'
order by table_name, conname;
