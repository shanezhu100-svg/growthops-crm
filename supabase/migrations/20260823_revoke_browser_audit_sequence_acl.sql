-- Post-P5 residual ACL hardening: the audit-log identity sequence is server-only.
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from anon;
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from authenticated;
