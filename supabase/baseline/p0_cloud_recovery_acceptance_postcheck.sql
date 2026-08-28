-- READ-ONLY post-check for the disposable cloud recovery acceptance.
-- Run only after p0_cloud_recovery_acceptance_sql_editor.sql on the same
-- disposable recovery target. This query never selects Vault plaintext.

with counts as (
  select
    (select count(*)::bigint from public.crm_users) as crm_users,
    (select count(*)::bigint from public.crm_workspaces) as crm_workspaces,
    (select count(*)::bigint from public.crm_sessions) as crm_sessions,
    (select count(*)::bigint from public.crm_server_audit_logs) as crm_server_audit_logs,
    (select count(*)::bigint from vault.secrets) as vault_secret_rows
)
select
  crm_users,
  crm_workspaces,
  crm_sessions,
  crm_server_audit_logs,
  vault_secret_rows,
  (
    crm_users = 0
    and crm_workspaces = 0
    and crm_sessions = 0
    and crm_server_audit_logs = 0
    and vault_secret_rows = 0
  ) as rollback_clean
from counts;
