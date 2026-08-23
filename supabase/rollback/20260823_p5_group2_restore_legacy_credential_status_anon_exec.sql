-- GrowthOps CRM P5 Group 2 emergency rollback
-- Restore exactly the pre-Group-2 anon EXECUTE grant for the legacy status RPC.

 grant execute on function public.crm_client_credential_status(text, text) to anon;
