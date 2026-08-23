-- Post-P5: minimize direct service_role CRM RPC surface.
-- Preserve exactly 11 BFF entry RPCs plus crm_bootstrap_admin.

revoke execute on function public.crm_cap_session_expiry_v2() from service_role;
revoke execute on function public.crm_client_credential_status(text,text) from service_role;
revoke execute on function public.crm_extract_live_secrets(jsonb) from service_role;
revoke execute on function public.crm_extract_secrets(jsonb) from service_role;
revoke execute on function public.crm_is_secret_key(text) from service_role;
revoke execute on function public.crm_limit_active_sessions_per_user() from service_role;
revoke execute on function public.crm_load_state(text) from service_role;
revoke execute on function public.crm_login(text,text) from service_role;
revoke execute on function public.crm_merge_secret_updates(jsonb,jsonb) from service_role;
revoke execute on function public.crm_prune_live_secrets(jsonb,jsonb) from service_role;
revoke execute on function public.crm_read_workspace_secrets(uuid) from service_role;
revoke execute on function public.crm_redact_secrets(jsonb) from service_role;
revoke execute on function public.crm_restore_role_restricted(text,jsonb,jsonb) from service_role;
revoke execute on function public.crm_restore_secrets(jsonb,jsonb) from service_role;
revoke execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from service_role;
revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from service_role;
revoke execute on function public.crm_reveal_client_secrets(text,text) from service_role;
revoke execute on function public.crm_revoke_unlocks_on_membership_security_change() from service_role;
revoke execute on function public.crm_revoke_unlocks_on_user_security_change() from service_role;
revoke execute on function public.crm_role_view_state(text,jsonb) from service_role;
revoke execute on function public.crm_secret_tree_nonempty(jsonb) from service_role;
revoke execute on function public.crm_secret_value_nonempty(jsonb) from service_role;
revoke execute on function public.crm_secret_value_text_v5(jsonb,text) from service_role;
revoke execute on function public.crm_session_context(text) from service_role;
revoke execute on function public.crm_strip_login_identifier_secrets(jsonb) from service_role;
revoke execute on function public.crm_token_hash(text) from service_role;
revoke execute on function public.crm_workspace_state_secret_guard() from service_role;
revoke execute on function public.crm_write_workspace_secrets(uuid,jsonb,uuid) from service_role;
