-- P5 Group 5: revoke transitional anon EXECUTE from authenticated session/workspace-state RPCs.
revoke execute on function public.crm_load_state_v3(text) from anon;
revoke execute on function public.crm_save_state(text, jsonb, bigint) from anon;
revoke execute on function public.crm_logout(text) from anon;
