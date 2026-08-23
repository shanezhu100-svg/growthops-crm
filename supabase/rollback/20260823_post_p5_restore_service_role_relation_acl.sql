-- Exact inverse for post-P5 service_role CRM relation ACL hardening.

grant select, insert, update, delete, truncate, references, trigger on table public.crm_credential_unlocks to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_server_audit_logs to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_sessions to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_setup_guard to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_users to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_workspace_members to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_workspace_secret_vault to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_workspace_state to service_role;
grant select, insert, update, delete, truncate, references, trigger on table public.crm_workspaces to service_role;
grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to service_role;
