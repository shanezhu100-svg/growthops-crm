-- Retire browser access to initialization and unused legacy v3 RPCs.
-- Current production adapter uses crm_login/crm_load_state; these v3 functions are retained only for rollback/service tooling.

revoke execute on function public.crm_bootstrap_admin(text,text,text,text) from anon, authenticated, public;
grant execute on function public.crm_bootstrap_admin(text,text,text,text) to service_role;

revoke execute on function public.crm_login_v3(text,text) from anon, authenticated, public;
grant execute on function public.crm_login_v3(text,text) to service_role;

revoke execute on function public.crm_load_state_v3(text) from anon, authenticated, public;
grant execute on function public.crm_load_state_v3(text) to service_role;

comment on function public.crm_bootstrap_admin(text,text,text,text) is
  'Initial provisioning RPC retired from browser roles after workspace/admin initialization; service_role only.';
comment on function public.crm_login_v3(text,text) is
  'Legacy compatibility login RPC retained for rollback only; service_role only.';
comment on function public.crm_load_state_v3(text) is
  'Legacy compatibility load RPC retained for rollback only; service_role only.';
