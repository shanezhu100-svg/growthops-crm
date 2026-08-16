-- Correction after auditing the full build chain.
-- security_finalize.py runs after p2_finalize.py and rewrites browser login/load
-- to the v3 RPCs, so these endpoints must remain callable from the public API
-- while enforcing CRM credentials/token validation internally.

grant execute on function public.crm_login_v3(text,text) to anon, authenticated, service_role;
grant execute on function public.crm_load_state_v3(text) to anon, authenticated, service_role;

comment on function public.crm_login_v3(text,text) is
  'Browser-exposed CRM login RPC used by the final security build; credential verification is enforced inside the function.';
comment on function public.crm_load_state_v3(text) is
  'Browser-exposed CRM state load RPC used by the final security build; a valid CRM token is enforced inside the function.';
