-- GrowthOps browser requests use the Supabase publishable key as anon and then
-- authenticate every protected operation with the CRM token. The Supabase
-- authenticated role is not part of this trust path, so do not grant it RPC
-- execution by default.

revoke execute on function public.crm_client_account_safe_summary(text,text) from authenticated;
revoke execute on function public.crm_client_credential_status(text,text) from authenticated;
revoke execute on function public.crm_delete_user(text,uuid) from authenticated;
revoke execute on function public.crm_list_users(text) from authenticated;
revoke execute on function public.crm_load_state(text) from authenticated;
revoke execute on function public.crm_load_state_v3(text) from authenticated;
revoke execute on function public.crm_login(text,text) from authenticated;
revoke execute on function public.crm_login_v3(text,text) from authenticated;
revoke execute on function public.crm_logout(text) from authenticated;
revoke execute on function public.crm_public_status() from authenticated;
revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from authenticated;
revoke execute on function public.crm_reveal_client_secrets(text,text) from authenticated;
revoke execute on function public.crm_save_state(text,jsonb,bigint) from authenticated;
revoke execute on function public.crm_unlock_credentials_v1(text,text) from authenticated;
revoke execute on function public.crm_upsert_user(text,uuid,text,text,text,text,boolean) from authenticated;
