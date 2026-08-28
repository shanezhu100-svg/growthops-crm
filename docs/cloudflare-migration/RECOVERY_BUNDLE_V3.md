# Recovery Bundle v3 Authority

Last reviewed: 2026-08-27

This document records the from-zero hosted Supabase recovery authority for GrowthOps CRM. It is recovery-test authority only; it does not authorize Production mutation or automatic rollback.

## Why Recovery Bundle v3 exists

The first authorized `schema.sql` proved that a real Production schema-only dump could be generated, but review found that database-level event-trigger objects and the safe migration ledger were outside that first artifact.

Recovery Bundle v2 added `event-triggers.sql` and a version/name-only `migration-ledger.sql`. A truly new hosted Supabase target then exposed a third portability boundary: a fresh project starts with platform default ACL state that can grant `anon`, `authenticated`, and `service_role` access to postgres-created objects before the restored event-trigger guards exist.

The first v2 from-zero attempt therefore observed correct RLS but inherited application-role ACLs. That was recovery-target default-ACL inheritance, not Production drift.

Recovery Bundle v3 adds:

`post-schema-security.sql`

The adjunct is intentionally narrow. It:

1. changes default privileges only for role `postgres` in schema `public`;
2. reconciles already-restored postgres-owned public relations, sequences, and functions;
3. revokes function EXECUTE from `PUBLIC`, `anon`, `authenticated`, and `service_role` before rebuilding the allowlist;
4. restores `service_role EXECUTE` to exactly 12 accepted CRM RPC signatures;
5. never alters `supabase_admin` default privileges;
6. never grants direct relation/function access to `anon` or `authenticated`;
7. contains no customer-row mutation.

The exact 12-RPC allowlist is pinned in:

`supabase/baseline/recovery_service_role_rpc_allowlist.txt`

The v3 workflow queries the authorized Production catalog and fails closed unless the live allowlist still matches that pinned file.

## Required restore order

On a **new, isolated, disposable Supabase project**, restore in exactly this order:

1. `schema.sql`
2. `event-triggers.sql`
3. `post-schema-security.sql`
4. `migration-ledger.sql`

Do not reorder steps 2 and 3. `post-schema-security.sql` reconciles objects that were restored before the event-trigger guards existed; the restored event triggers then protect future DDL after the recovery checkpoint.

## Accepted Recovery Bundle v3 artifact

Recovery Schema Bundle v3 workflow run `33079493119` completed successfully from protected:

`main@89e1904a521c41ab1b35eb29ef25c2834bf76538`

Accepted artifact evidence:

- artifact: `growthops-schema-recovery-bundle-v3-33079493119`;
- artifact ID: `9649406110`;
- artifact ZIP SHA-256: `c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7`;
- artifact size: `22424` bytes;
- artifact file count: `12`;
- `schema.sql`: `100993` bytes;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`;
- `event-triggers.sql`: exactly four `CREATE EVENT TRIGGER` statements;
- `migration-ledger.txt`: exactly 51 entries with head `20260825075808|post_p5_rate_limit_concurrency`;
- `post-schema-security.sql`: exactly 12 explicit CRM `service_role EXECUTE` grants;
- `post-schema-security.sql` SHA-256: `d811cfa142e2268b4ef4746f7bc87f837cc21b590b3716a3f834b68b36abbfe0`;
- zero `supabase_admin` default-ACL alterations in `post-schema-security.sql`;
- zero `anon` / `authenticated` grants in `post-schema-security.sql`;
- every file listed in `recovery-files.sha256` independently verified `OK`;
- metadata records `contains_customer_rows=false`, `contains_migration_statement_arrays=false`, `touches_supabase_admin_defaults=false`, and `empty_target_restore_required=true`.

The workflow logs kept `SUPABASE_DB_URL` masked as `***`; no database password, complete PostgreSQL URL, or Supabase server secret was observed in the run logs.

This accepts the **integrity and scope of the v3 artifact**. Full recovery acceptance additionally required the hosted restore and synthetic rollback checks below.

## Fresh hosted v3 restore proof

The second truly fresh hosted recovery target is:

`qczkskuaszlezlcxxpqk / growthops-recovery-bundle-v3-test / ap-southeast-1`

Its pre-restore application start was independently verified as:

- public tables: `0`;
- public routines: `0`;
- public event triggers: `0`;
- application migration table: absent.

After restoring the accepted v3 artifact in the documented order, the target reached the accepted Production comparison checkpoints:

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- supplemental guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public recovery fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- safe migration ledger: exactly `51` entries;
- migration head: `20260825075808 / post_p5_rate_limit_concurrency`;
- CRM RLS: `9 / 9`;
- CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`;
- expected database-level event triggers: `4`.

The four database-level event triggers are `ensure_rls`, `growthops_crm_acl_guard_ddl`, `growthops_crm_rls_guard_ddl`, and `growthops_public_noncrm_function_acl_guard_ddl`.

A transaction-contained future-object probe then proved automatic RLS enablement and fail-closed ACL behavior for a new CRM table, sequence, CRM function, and non-CRM public function. The transaction rolled back and all four synthetic probe objects were subsequently proven absent.

The recovery target remained empty of synthetic business/Vault data after catalog and future-object verification: `crm_users=0`, `crm_workspaces=0`, `crm_sessions=0`, `crm_server_audit_logs=0`, and `vault.secrets=0`.

Supabase Security Advisor returned only expected `RLS enabled / no policy` INFO notices for the RPC-only/default-deny CRM tables. Performance Advisor returned only unused-index INFO notices expected on a newly restored database with no business traffic. Those notices do not authorize schema changes.

Detailed evidence is retained in:

`docs/cloudflare-migration/FRESH_V3_HOSTED_RESTORE_20260827.md`

### Recovery transport correction disclosure

The connected SQL transport cannot send the approximately 100 KB `schema.sql` as one payload, so the restore harness transported the original file in seven statement-boundary batches. The first fingerprint pass exposed one transport transcription defect: an obsolete unused `k text;` declaration had been introduced into `public.crm_role_view_state(text,jsonb)` by the transport batch.

Direct inspection of the accepted ZIP proved the bundled `schema.sql` did **not** contain that declaration and matched live Production. The disposable target was corrected only by re-applying the exact original function definition from the accepted artifact, and the transport-only migration entry was removed. This was an executor transcription correction, not a Bundle v3 schema/security repair or Production mutation. The issue audit entry was corrected in place rather than leaving the wrong attribution in history.

## Final synthetic cloud acceptance — passed

The canonical psql acceptance is:

`supabase/baseline/p0_cloud_recovery_acceptance.sql`

The Gate-pinned Supabase-compatible derivative is:

`supabase/baseline/p0_cloud_recovery_acceptance_sql_editor.sql`

On 2026-08-27 the complete Gate-pinned derivative was executed through the connected Supabase SQL executor against only the disposable v3 target `qczkskuaszlezlcxxpqk`. The transaction completed its assertions, rolled back, and returned:

`P0_CLOUD_RECOVERY_ACCEPTANCE_OK`

The immediate read-only/count-only:

`supabase/baseline/p0_cloud_recovery_acceptance_postcheck.sql`

returned:

- `crm_users = 0`;
- `crm_workspaces = 0`;
- `crm_sessions = 0`;
- `crm_server_audit_logs = 0`;
- `vault_secret_rows = 0`;
- `rollback_clean = true`.

Independent post-acceptance catalog verification then re-confirmed:

- primary `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- guard `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- migration ledger exactly `51` entries;
- migration head `20260825075808 / post_p5_rate_limit_concurrency`.

This completes the technical zero-to-current recovery acceptance for issue #93. The disposable-project lifecycle remains an operational cleanup choice; it does not invalidate the accepted proof.

## Safety boundaries

- Never run `p0_cloud_recovery_acceptance.sql` or its SQL Editor derivative against Production.
- Never export customer rows or Vault plaintext into the recovery bundle.
- Never print or commit a database password, full credential-bearing PostgreSQL URL, Supabase server secret, or customer secret material.
- A service-role/API secret is not a PostgreSQL database password.
- Do not modify `supabase_admin` defaults to force a recovery fingerprint match.
- A fingerprint mismatch is an investigation trigger, not authorization to repair Production.
