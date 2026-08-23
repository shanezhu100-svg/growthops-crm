-- Emergency rollback for the Post-P5 CRM ALTER-table RLS guard.
-- Existing ensure_rls and the CRM ACL guard are intentionally left untouched.
drop event trigger if exists growthops_crm_rls_guard_ddl;
drop function if exists public.growthops_crm_rls_guard_ddl();
