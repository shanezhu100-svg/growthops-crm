-- Emergency rollback for P5 Group 4: restore only the removed safe-summary anon EXECUTE grant.
grant execute on function public.crm_client_account_safe_summary(text, text) to anon;
