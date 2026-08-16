-- Final browser builds use crm_login_v3 / crm_load_state_v3 so state is
-- recursively redacted before it reaches the client. Keep the underlying
-- crm_login / crm_load_state implementations internal-only to prevent bypassing
-- the v3 redaction wrapper.

revoke execute on function public.crm_login(text,text) from anon, authenticated, public;
revoke execute on function public.crm_load_state(text) from anon, authenticated, public;
grant execute on function public.crm_login(text,text) to service_role;
grant execute on function public.crm_load_state(text) to service_role;

comment on function public.crm_login(text,text) is
  'Internal base login implementation. Browser access is intentionally disabled; final CRM clients use crm_login_v3 so returned state is recursively redacted.';
comment on function public.crm_load_state(text) is
  'Internal base state loader. Browser access is intentionally disabled; final CRM clients use crm_load_state_v3 so returned state is recursively redacted.';
