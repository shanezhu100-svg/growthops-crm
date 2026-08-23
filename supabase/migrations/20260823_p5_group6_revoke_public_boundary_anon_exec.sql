-- P5 Group 6: revoke transitional anon EXECUTE from the two public-entry RPCs.
revoke execute on function public.crm_login_v3(text, text) from anon;
revoke execute on function public.crm_public_status() from anon;
