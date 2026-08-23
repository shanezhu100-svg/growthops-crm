-- Emergency rollback for P5 Group 3: restore only the three removed anon EXECUTE grants.
grant execute on function public.crm_list_users(text) to anon;
grant execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) to anon;
grant execute on function public.crm_delete_user(text, uuid) to anon;
