# P0 Supabase Migration Ledger

Original checkpoint date: 2026-08-21
Last consolidated from Production: 2026-08-30

This document records the live `supabase_migrations.schema_migrations` ledger observed for GrowthOps CRM and distinguishes it from SQL files currently present in the repository. The original 2026-08-21 baseline remains visible below; later forward migrations are consolidated into the same authority without rewriting or guessing the unresolved 2026-08-13/14 historical SQL gap.

## Original live remote ledger checkpoint

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

The repository also contains `supabase/migrations/20260815_security_vault_enforce.sql`. It is part of the retained security migration source set, but the live ledger does not show a separate migration name `security_vault_enforce`. Do not infer a new remote history entry from the filename alone.

## Consolidated forward ledger

The Production ledger was re-read on 2026-08-30 after the client-account correspondence migration. The entries below are genuine forward migrations after the original 2026-08-21 checkpoint and each maps to retained repository SQL.

| Remote version | Migration name | Repository file |
| --- | --- | --- |
| `20260822151709` | `p5_revoke_sensitive_anon_exec_group1` | `supabase/migrations/20260822_p5_revoke_sensitive_anon_exec.sql` |
| `20260823045642` | `credential_unlock_reauth_bridge` | `supabase/migrations/20260823_credential_unlock_reauth_bridge.sql` |
| `20260823062545` | `p5_group2_revoke_legacy_credential_status_anon_exec` | `supabase/migrations/20260823_p5_group2_revoke_legacy_credential_status_anon_exec.sql` |
| `20260823064535` | `p5_group3_revoke_admin_user_mgmt_anon_exec` | `supabase/migrations/20260823_p5_group3_revoke_admin_user_mgmt_anon_exec.sql` |
| `20260823071407` | `p5_group4_revoke_safe_summary_anon_exec` | `supabase/migrations/20260823_p5_group4_revoke_safe_summary_anon_exec.sql` |
| `20260823085810` | `p5_group5_revoke_session_state_anon_exec` | `supabase/migrations/20260823_p5_group5_revoke_session_state_anon_exec.sql` |
| `20260823101656` | `p5_group6_revoke_public_boundary_anon_exec` | `supabase/migrations/20260823_p5_group6_revoke_public_boundary_anon_exec.sql` |
| `20260823104232` | `post_p5_revoke_browser_audit_sequence_acl` | `supabase/migrations/20260823_revoke_browser_audit_sequence_acl.sql` |
| `20260823120150` | `post_p5_minimize_service_role_rpc_exec` | `supabase/migrations/20260823_revoke_internal_service_role_exec.sql` |
| `20260823123328` | `post_p5_revoke_service_role_relation_acl` | `supabase/migrations/20260823_post_p5_revoke_service_role_relation_acl.sql` |
| `20260823131002` | `post_p5_login_trusted_source_bucket` | `supabase/migrations/20260823_post_p5_login_trusted_source_bucket.sql` |
| `20260823135410` | `post_p5_crm_acl_event_guard` | `supabase/migrations/20260823_post_p5_crm_acl_event_guard.sql` |
| `20260823143620` | `post_p5_crm_rls_alter_guard` | `supabase/migrations/20260823_post_p5_crm_rls_alter_guard.sql` |
| `20260824005806` | `post_p5_v5_direct_scalar` | `supabase/migrations/20260824_post_p5_v5_direct_scalar.sql` |
| `20260824023041` | `post_p5_bcrypt_password_byte_cap` | `supabase/migrations/20260824_post_p5_bcrypt_password_byte_cap.sql` |
| `20260824031539` | `post_p5_single_workspace_membership_invariant` | `supabase/migrations/20260824_post_p5_single_workspace_membership_invariant.sql` |
| `20260824031938` | `post_p5_bcrypt_verification_byte_caps` | `supabase/migrations/20260824_post_p5_bcrypt_verification_byte_caps.sql` |
| `20260824034405` | `post_p5_user_identity_byte_caps` | `supabase/migrations/20260824_post_p5_user_identity_byte_caps.sql` |
| `20260825032049` | `post_p5_revoke_rls_auto_enable_service_role_exec` | `supabase/migrations/20260824_post_p5_revoke_rls_auto_enable_service_role_exec.sql` |
| `20260825040850` | `post_p5_public_default_privilege_guard` | `supabase/migrations/20260824_post_p5_public_default_privilege_guard.sql` |
| `20260825075808` | `post_p5_rate_limit_concurrency` | `supabase/migrations/20260825_post_p5_rate_limit_concurrency.sql` |
| `20260830071649` | `client_account_safe_summary_correspondence` | `supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql` |

The `20260825075808` migration retains its exact rollback, preflight, read-only post-check, canonical regression test, and acceptance record. The new `20260830071649` migration is a forward-compatible replacement of `crm_client_account_safe_summary(text,text)` and retains its matching rollback at `supabase/rollback/20260830071649_client_account_safe_summary_correspondence.sql`; it does not change customer rows or broaden application-role privileges.

As of the 2026-08-30 Production re-read, there is no newly observed remote-history-only migration after 2026-08-14. The unresolved historical gap remains exactly the eleven 2026-08-13/14 entries listed above; do not blur that known gap with later forward migrations that are present in GitHub.

`P0_MIGRATION_LEDGER_20260825_APPENDIX.md` is retained as point-in-time acceptance evidence for the concurrency migration. Its information is historical; this main ledger is the consolidated current remote migration-history authority.

## Current recovery comparison anchors

Fresh read-only Production evidence after `20260830071649` is:

- primary CRM fingerprint: `200 / 8ff7dd1447bf2cea9802438f91e8e1d3bf34bc7f7b4878592dd2eca8b06da7f9`;
- supplemental three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- supplemental wider-public recovery fingerprint: `225 / b89328f5548d4787a650b7f079bc1843125cc7c1b550d959a8cb4df2b2df04f2`;
- current Production migration head: `20260830071649 / client_account_safe_summary_correspondence`;
- current Production migration rows: `52`.

The immediately preceding accepted checkpoint remains historical evidence: `20260825075808 / post_p5_rate_limit_concurrency`, primary `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`, wider-public `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`.

Recovery Bundle v3 remains an accepted, independently restored **51-migration recovery base** through `20260825075808`; do not rewrite its historical artifact metadata. Until a newer portable bundle is generated and independently accepted, recovery to the current Production schema is **Recovery Bundle v3 followed by the repository-backed forward migration `20260830071649_client_account_safe_summary_correspondence.sql`**, then fresh fingerprints/ACL checks.

These deterministic fingerprints are comparison anchors only. They do not replace an authorized portable schema artifact plus forward migrations and restore verification.

## Recovery rule

The eleven 2026-08-13/14 entries above are historical facts, but their original SQL is not present in the current repository. We must not synthesize guessed SQL and label it as the historical original.

For recovery and Cloudflare migration safety:

1. Preserve this exact remote ledger.
2. Preserve the current live schema/security inventory and validation queries.
3. Preserve all genuine SQL migration files currently in `supabase/migrations`.
4. Use the accepted schema dump/export as structural recovery base and apply repository-backed forward migrations after its ledger head.
5. Treat later schema changes as forward migrations committed to the repository.
6. Before a destructive database restore, verify Vault handling separately; ordinary backups must not contain credential values.

## Cloudflare migration implication

This ledger gap blocks claiming “all historical Supabase migrations are stored in GitHub,” but it does **not** require reconstructing historical SQL before hosting work. Hosting changes must not alter Supabase unless they are accompanied by an explicit reviewed database migration.

Before any later database permission/function/schema change, the current schema/security baseline, wider recovery fingerprint when relevant, and new migration SQL must be committed and independently validated.
