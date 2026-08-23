-- Emergency rollback for P5 Group 6: restore only the two removed anon EXECUTE grants.
grant execute on function public.crm_login_v3(text, text) to anon;
grant execute on function public.crm_public_status() to anon;
