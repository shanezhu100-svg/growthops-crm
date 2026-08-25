-- Post-P5: remove the historical event-trigger helper from the BFF service-role surface.
-- The ensure_rls event trigger is owned by postgres and remains bound to this function;
-- revoking service_role EXECUTE only removes direct invocation through that role.

revoke execute on function public.rls_auto_enable() from service_role;
