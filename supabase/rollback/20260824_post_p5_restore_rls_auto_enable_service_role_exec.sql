-- Exact rollback for the historical event-trigger helper ACL only.

grant execute on function public.rls_auto_enable() to service_role;
