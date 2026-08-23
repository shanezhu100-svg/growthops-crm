-- Roll back only the future-DDL ACL guard.
-- This intentionally does not broaden ACLs on any objects that may have been
-- created while the guard was active.

drop event trigger if exists growthops_crm_acl_guard_ddl;
drop function if exists public.growthops_crm_acl_guard_ddl();
