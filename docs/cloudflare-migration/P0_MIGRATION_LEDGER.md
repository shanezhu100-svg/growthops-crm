# P0 Supabase Migration Ledger

Checkpoint date: 2026-08-21

This document records the live `supabase_migrations.schema_migrations` ledger observed before Cloudflare migration and distinguishes it from SQL files currently present in the repository.

## Live remote ledger

| Remote version | Migration name | Repository status |
| --- | --- | --- |
| `20260813095251` | `growthops_cloud_auth_and_state` | **remote-history-only; original SQL absent from current repo** |
| `20260813095804` | `protect_initial_admin_bootstrap` | **remote-history-only; original SQL absent from current repo** |
| `20260813100059` | `enforce_role_state_redaction` | **remote-history-only; original SQL absent from current repo** |
| `20260813111307` | `harden_crm_internal_functions` | **remote-history-only; original SQL absent from current repo** |
| `20260813111638` | `hide_crm_internal_rpc_helpers` | **remote-history-only; original SQL absent from current repo** |
| `20260814033422` | `fix_role_state_and_secret_restore` | **remote-history-only; original SQL absent from current repo** |
| `20260814035507` | `tighten_role_state_visibility` | **remote-history-only; original SQL absent from current repo** |
| `20260814050602` | `revoke_old_sessions_on_password_change` | **remote-history-only; original SQL absent from current repo** |
| `20260814063130` | `redact_login_accounts_for_restricted_roles` | **remote-history-only; original SQL absent from current repo** |
| `20260814063224` | `redact_legacy_platform_login_fields` | **remote-history-only; original SQL absent from current repo** |
| `20260814064217` | `restrict_cloud_backups_to_admin` | **remote-history-only; original SQL absent from current repo** |
| `20260815142129` | `p2_login_audit_rate_limit` | repo file: `supabase/migrations/20260815_p2_login_audit_rate_limit.sql` |
| `20260815152918` | `security_vault_stage` | repo file: `supabase/migrations/20260815_security_vault_stage.sql` |
| `20260816084942` | `credential_reveal_hardening` | repo file: `supabase/migrations/20260816_credential_reveal_hardening.sql` |
| `20260816085757` | `credential_reveal_rate_window_v2` | repo file: `supabase/migrations/20260816_credential_reveal_rate_window_v2.sql` |
| `20260816090730` | `client_credential_status` | repo file: `supabase/migrations/20260816_client_credential_status.sql` |
| `20260816095326` | `client_account_safe_summary` | repo file: `supabase/migrations/20260816_client_account_safe_summary.sql` |
| `20260816101044` | `credential_field_reveal_v3` | repo file: `supabase/migrations/20260816_credential_field_reveal_v3.sql` |
| `20260816101605` | `credential_unlock_v4` | repo file: `supabase/migrations/20260816_credential_unlock_v4.sql` |
| `20260816102212` | `workspace_state_secret_hard_guard` | repo file: `supabase/migrations/20260816_workspace_state_secret_hard_guard.sql` |
| `20260816102846` | `retire_unused_bootstrap_and_v3_rpcs` | repo file: `supabase/migrations/20260816_retire_unused_bootstrap_and_v3_rpcs.sql` |
| `20260816102939` | `add_fk_covering_indexes` | repo file: `supabase/migrations/20260816_add_fk_covering_indexes.sql` |
| `20260816103122` | `restore_v3_browser_exec_after_build_chain_audit` | repo file: `supabase/migrations/20260816_z_restore_v3_browser_exec_after_build_chain_audit.sql` |
| `20260816103646` | `revoke_credential_unlocks_on_identity_change` | repo file: `supabase/migrations/20260816_revoke_credential_unlocks_on_identity_change.sql` |
| `20260816103810` | `revoke_unused_authenticated_rpc_exec` | repo file: `supabase/migrations/20260816_revoke_unused_authenticated_rpc_exec.sql` |
| `20260816103855` | `retire_direct_legacy_login_load_rpc` | repo file: `supabase/migrations/20260816_retire_direct_legacy_login_load_rpc.sql` |
| `20260816104215` | `default_deny_public_schema_for_crm` | repo file: `supabase/migrations/20260816_default_deny_public_schema_for_crm.sql` |
| `20260816104413` | `limit_active_sessions_per_user` | repo file: `supabase/migrations/20260816_limit_active_sessions_per_user.sql` |
| `20260821074838` | `credential_surface_session_hardening_v2` | repo file: `supabase/migrations/20260821_credential_surface_session_hardening.sql` |
| `20260821091200` | `credential_minimal_reveal_v5` | repo file: `supabase/migrations/20260821_credential_minimal_reveal_v5.sql` |

## Additional repository migration

The repository also contains `supabase/migrations/20260815_security_vault_enforce.sql`. It is part of the retained security migration source set, but the live ledger query captured above did not show a separate migration name `security_vault_enforce`. Do not infer a new remote history entry from the filename alone.

## Recovery rule

The eleven 2026-08-13/14 entries above are historical facts, but their original SQL is not present in the current repository. We must not synthesize guessed SQL and label it as the historical original.

For recovery and Cloudflare migration safety:

1. Preserve this exact remote ledger.
2. Preserve the current live schema/security inventory and validation queries.
3. Preserve all genuine SQL migration files currently in `supabase/migrations`.
4. Use a real database schema dump/export when available as the authoritative structural snapshot.
5. Treat later schema changes as forward migrations committed to the repository.
6. Before a destructive database restore, verify Vault handling separately; ordinary backups must not contain credential values.

## Cloudflare migration implication

This ledger gap blocks claiming “all historical Supabase migrations are stored in GitHub,” but it does **not** require reconstructing historical SQL before P1 static Preview. P1 changes hosting only and must not change Supabase.

Before any P2/P5 database permission change, the current schema/security baseline and new migration SQL must be committed and independently validated.
