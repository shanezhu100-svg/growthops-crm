-- GrowthOps Recovery Bundle v3 post-schema security reconciliation.
--
-- Apply ONLY to a new isolated disposable recovery project after schema.sql and
-- event-triggers.sql. This file repairs the Supabase new-project postgres/public
-- default-ACL inheritance gap discovered by the 2026-08-27 from-zero restore.
--
-- Scope is intentionally narrow:
--   * postgres-owned objects in public;
--   * postgres default privileges in public;
--   * exact service_role EXECUTE allowlist for 12 accepted CRM RPCs.
--
-- It must never alter supabase_admin default privileges or grant browser roles
-- direct CRM relation/function access.

begin;

-- Match Production future-object defaults for objects subsequently created by
-- postgres in public. Supabase platform-owned supabase_admin defaults are out of
-- scope and must remain untouched.
alter default privileges for role postgres in schema public
  revoke all privileges on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke all privileges on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated, service_role;

-- Reconcile already-restored postgres-owned public relations/functions that were
-- created before the database-level ACL event triggers existed on the fresh
-- recovery target.
do $recovery_acl$
declare
  r record;
begin
  for r in
    select n.nspname, c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r','p','v','m','f')
      and pg_get_userbyid(c.relowner) = 'postgres'
    order by c.relname
  loop
    execute format(
      'revoke all privileges on table %I.%I from anon, authenticated, service_role',
      r.nspname, r.relname
    );
  end loop;

  for r in
    select n.nspname, c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind = 'S'
      and pg_get_userbyid(c.relowner) = 'postgres'
    order by c.relname
  loop
    execute format(
      'revoke all privileges on sequence %I.%I from anon, authenticated, service_role',
      r.nspname, r.relname
    );
  end loop;

  for r in
    select n.nspname, p.proname, oidvectortypes(p.proargtypes) as argtypes
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.prokind = 'f'
      and pg_get_userbyid(p.proowner) = 'postgres'
    order by p.proname, oidvectortypes(p.proargtypes)
  loop
    execute format(
      'revoke execute on function %I.%I(%s) from public, anon, authenticated, service_role',
      r.nspname, r.proname, r.argtypes
    );
  end loop;
end
$recovery_acl$;

-- Restore only the accepted server-side RPC surface.
grant execute on function public.crm_bootstrap_admin(text,text,text,text) to service_role;
grant execute on function public.crm_client_account_safe_summary(text,text) to service_role;
grant execute on function public.crm_delete_user(text,uuid) to service_role;
grant execute on function public.crm_list_users(text) to service_role;
grant execute on function public.crm_load_state_v3(text) to service_role;
grant execute on function public.crm_login_v3(text,text) to service_role;
grant execute on function public.crm_logout(text) to service_role;
grant execute on function public.crm_public_status() to service_role;
grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) to service_role;
grant execute on function public.crm_save_state(text,jsonb,bigint) to service_role;
grant execute on function public.crm_unlock_credentials_v1(text,text) to service_role;
grant execute on function public.crm_upsert_user(text,uuid,text,text,text,text,boolean) to service_role;

commit;
