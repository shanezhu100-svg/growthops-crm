-- Emergency rollback for P5 Group 5: restore only the three removed anon EXECUTE grants.
grant execute on function public.crm_load_state_v3(text) to anon;
grant execute on function public.crm_save_state(text, jsonb, bigint) to anon;
grant execute on function public.crm_logout(text) to anon;
