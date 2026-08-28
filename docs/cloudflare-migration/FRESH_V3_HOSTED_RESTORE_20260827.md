# Fresh Hosted Recovery Bundle v3 Restore Evidence — 2026-08-27

This document records the second truly fresh hosted Supabase restore used to validate the accepted GrowthOps CRM Recovery Bundle v3 artifact. It is recovery evidence only. It does not authorize Production mutation or automatic repair.

## Target and safety boundary

Disposable target:

`qczkskuaszlezlcxxpqk / growthops-recovery-bundle-v3-test / ap-southeast-1`

The project was created only after the selected Supabase organization reported a current project cost of `$0/month`. Production was not modified. The preceding disposable v2 recovery target was paused to free the Free Plan active-project slot; it was not deleted.

Before restore, read-only catalog inspection proved a genuinely empty application start:

- public tables: `0`;
- public routines: `0`;
- public event triggers: `0`;
- application migration table: absent.

No customer rows or Vault plaintext were copied into the target.

## Artifact under test

Accepted Recovery Bundle v3 artifact:

- workflow run: `33079493119`;
- source: `main@89e1904a521c41ab1b35eb29ef25c2834bf76538`;
- artifact: `growthops-schema-recovery-bundle-v3-33079493119`;
- artifact ID: `9649406110`;
- ZIP SHA-256: `c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7`;
- file count: `12`;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`.

The ZIP and its internal `recovery-files.sha256` manifest were independently verified before this restore.

## Restore order

The restore followed the v3 authority order:

1. `schema.sql`
2. `event-triggers.sql`
3. `post-schema-security.sql`
4. `migration-ledger.sql`

`post-schema-security.sql` was applied as the bundle-provided reconciliation. No ad-hoc ACL broadening or Production mutation was used.

Because the connected SQL transport cannot send the approximately 100 KB `schema.sql` as one payload, the original file was transported in seven statement-boundary batches. A transport transcription defect was detected after the first fingerprint pass: one batch had introduced an obsolete, unused `k text;` declaration into `public.crm_role_view_state(text,jsonb)`.

Direct inspection of the accepted ZIP proved that the bundled `schema.sql` did **not** contain that declaration and matched the live Production definition. The recovery target was therefore corrected only by re-applying the exact original function definition from the accepted bundle, and the transport-only migration entry was removed. This was a recovery-executor transcription correction, not a Bundle v3 schema/security repair. The earlier issue comment that briefly attributed the mismatch to the bundle was corrected in place.

## Accepted catalog and security result

After the transport correction from the original bundle, the disposable hosted target matched every accepted Production comparison checkpoint exactly:

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- supplemental guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- safe migration ledger: exactly `51` entries;
- migration head: `20260825075808 / post_p5_rate_limit_concurrency`;
- CRM RLS: `9 / 9`;
- CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`;
- expected database-level event triggers: `4`.

The four event triggers are:

- `ensure_rls` → `public.rls_auto_enable()`;
- `growthops_crm_acl_guard_ddl` → `public.growthops_crm_acl_guard_ddl()`;
- `growthops_crm_rls_guard_ddl` → `public.growthops_crm_rls_guard_ddl()`;
- `growthops_public_noncrm_function_acl_guard_ddl` → `public.growthops_public_noncrm_function_acl_guard_ddl()`.

A read-only Production recheck during the investigation remained at the accepted primary `200 / 77ba3a7c...` and 51-entry migration head, so the temporary mismatch was not Production drift.

## Future-object fail-closed probe

A transaction-contained synthetic future-object probe created:

- one `crm_*` table;
- one `crm_*` sequence;
- one `crm_*` function;
- one non-CRM public function.

The probe required:

- automatic RLS enablement on the new CRM table;
- no application-role relation privileges;
- no application-role sequence privileges;
- no `anon`, `authenticated`, or `service_role` EXECUTE on the new CRM function;
- no `PUBLIC`, `anon`, `authenticated`, or `service_role` EXECUTE on the new non-CRM public function.

All assertions passed. The transaction rolled back, and a subsequent read-only check proved all four synthetic objects absent.

## Empty-data post-check

After restore and future-object probing, the disposable target still had:

- `crm_users = 0`;
- `crm_workspaces = 0`;
- `crm_sessions = 0`;
- `crm_server_audit_logs = 0`;
- `vault.secrets = 0`.

This confirms the catalog/security verification and future-object probe did not leave synthetic business or Vault data behind.

## Advisor review

Supabase Security Advisor reported only `RLS enabled / no policy` INFO notices for the nine CRM tables. This is expected under the accepted RPC-only/default-deny design and does not authorize adding browser-facing policies.

Supabase Performance Advisor reported only unused-index INFO notices. The target is a newly restored database with no business traffic, so those notices are expected and do not authorize dropping recovery-restored indexes.

## Remaining closure item

Issue #93 remains open for exactly one substantive acceptance item:

`supabase/baseline/p0_cloud_recovery_acceptance.sql`

That script has been statically reviewed to use synthetic values only, require an empty CRM target, run inside an explicit transaction, emit `P0_CLOUD_RECOVERY_ACCEPTANCE_OK` only after its assertions, and end with `ROLLBACK`.

The connected SQL execution safety layer blocks the credential/reveal payload before it reaches Postgres. Therefore the full synthetic cloud acceptance has **not** yet executed successfully in this recovery run and must not be claimed as passed.

Run that script only in the disposable target above, never in Production. After it reports success, independently verify that CRM users/workspaces/sessions/audit rows and Vault synthetic rows returned to zero before closing #93.
