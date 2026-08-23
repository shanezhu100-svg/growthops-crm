-- P5 Group 4: revoke transitional anon EXECUTE from the server-mediated credential safe-summary RPC.
revoke execute on function public.crm_client_account_safe_summary(text, text) from anon;
