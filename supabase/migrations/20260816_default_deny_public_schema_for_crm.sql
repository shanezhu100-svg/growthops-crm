-- CRM objects are created by postgres. Default-deny browser database roles so
-- every browser-facing RPC requires an explicit grant in its own migration.
-- This prevents future tables/functions/sequences from being exposed merely
-- because a migration forgot an explicit REVOKE.

alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke execute on functions from anon, authenticated;

-- service_role defaults remain intact for internal maintenance/server tooling.
comment on schema public is
  'GrowthOps CRM security posture: postgres-created public objects default-deny anon/authenticated. Browser RPCs must be explicitly granted to anon and perform CRM token/role checks internally.';
