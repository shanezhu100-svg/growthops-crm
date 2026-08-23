-- P5 Group 3: revoke transitional anon EXECUTE from the three server-mediated ADMIN user-management RPCs.
revoke execute on function public.crm_list_users(text) from anon;
revoke execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) from anon;
revoke execute on function public.crm_delete_user(text, uuid) from anon;
