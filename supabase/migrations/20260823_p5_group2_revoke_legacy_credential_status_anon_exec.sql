-- GrowthOps CRM P5 Group 2
-- Retire the legacy credential-status RPC from the transitional anon surface.
-- Privilege-only migration: no function body, table, RLS, policy, Vault, Session,
-- or application-state change is permitted in this file.

revoke execute on function public.crm_client_credential_status(text, text) from anon;
