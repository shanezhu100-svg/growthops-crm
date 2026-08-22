-- P5 group 1: remove browser-anon execution from the two sensitive
-- credential RPCs only. Both Cloudflare and Vercel BFFs call Supabase with
-- GROWTHOPS_SUPABASE_SECRET_KEY and therefore execute as service_role.
--
-- Deliberately unchanged in this migration:
-- - function definitions
-- - service_role EXECUTE
-- - authenticated privileges
-- - login/public/state/user-management RPC privileges
-- - tables, RLS, policies, Vault, sessions, or application data

begin;

revoke execute on function public.crm_unlock_credentials_v1(text, text) from anon;
revoke execute on function public.crm_reveal_client_secret_value_v5(text, text, text, text, text, text) from anon;

commit;
