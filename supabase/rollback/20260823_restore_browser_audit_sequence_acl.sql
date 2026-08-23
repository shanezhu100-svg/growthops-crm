-- Emergency rollback: restore only the pre-hardening browser-role sequence ACL.
grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to anon;
grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to authenticated;
