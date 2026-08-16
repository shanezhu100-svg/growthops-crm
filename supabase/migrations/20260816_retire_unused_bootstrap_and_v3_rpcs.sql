-- Retire only the one-time browser bootstrap entry after initialization.
-- IMPORTANT: the final production build runs security_finalize.py after p2_finalize.py,
-- and that finalizer intentionally rewrites login/load calls to crm_login_v3 and
-- crm_load_state_v3. Those two RPCs therefore MUST remain browser-callable and
-- continue to enforce CRM authentication internally.

revoke execute on function public.crm_bootstrap_admin(text,text,text,text) from anon, authenticated, public;
grant execute on function public.crm_bootstrap_admin(text,text,text,text) to service_role;

-- Explicitly preserve the final-build login/load endpoints.
grant execute on function public.crm_login_v3(text,text) to anon, authenticated, service_role;
grant execute on function public.crm_load_state_v3(text) to anon, authenticated, service_role;

comment on function public.crm_bootstrap_admin(text,text,text,text) is
  'Initial provisioning RPC retired from browser roles after workspace/admin initialization; service_role only.';
comment on function public.crm_login_v3(text,text) is
  'Browser-exposed CRM login RPC used by the final security build; credential verification is enforced inside the function.';
comment on function public.crm_load_state_v3(text) is
  'Browser-exposed CRM state load RPC used by the final security build; a valid CRM token is enforced inside the function.';
