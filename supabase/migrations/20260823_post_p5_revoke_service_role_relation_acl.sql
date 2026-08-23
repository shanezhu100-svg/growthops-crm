-- Post-P5: remove direct service_role access to CRM relations.
-- BFF access remains through the 12 preserved SECURITY DEFINER function entries.

revoke all privileges on table public.crm_credential_unlocks from service_role;
revoke all privileges on table public.crm_server_audit_logs from service_role;
revoke all privileges on table public.crm_sessions from service_role;
revoke all privileges on table public.crm_setup_guard from service_role;
revoke all privileges on table public.crm_users from service_role;
revoke all privileges on table public.crm_workspace_members from service_role;
revoke all privileges on table public.crm_workspace_secret_vault from service_role;
revoke all privileges on table public.crm_workspace_state from service_role;
revoke all privileges on table public.crm_workspaces from service_role;
revoke all privileges on sequence public.crm_server_audit_logs_id_seq from service_role;
