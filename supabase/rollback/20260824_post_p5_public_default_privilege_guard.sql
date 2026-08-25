-- Exact rollback for 20260824_post_p5_public_default_privilege_guard.sql.
-- Restores the pre-migration postgres-created public defaults for service_role
-- and removes only the new non-CRM function/procedure event-trigger guard.

drop event trigger if exists growthops_public_noncrm_function_acl_guard_ddl;
drop function if exists public.growthops_public_noncrm_function_acl_guard_ddl();

alter default privileges for role postgres in schema public
  grant all privileges on tables to service_role;

alter default privileges for role postgres in schema public
  grant all privileges on sequences to service_role;

alter default privileges for role postgres in schema public
  grant execute on functions to service_role;
