# Current CRM Recovery Verification

Last reviewed: 2026-08-27

This is the current verification entrypoint for GrowthOps CRM recovery and database-change rollback acceptance. Recovery Bundle v3 has now been generated from protected `main`, independently checksum-inspected, and restored into a second truly fresh hosted Supabase project with the accepted catalog/security fingerprints and migration head. Issue #93 remains open for one final substantive step only: the transaction-contained synthetic cloud recovery acceptance and its rollback-clean post-check. This runbook does **not** authorize automatic Production repair.

Use this runbook with `CURRENT_STATE.md`, `FULL_SCHEMA_EXPORT.md`, `RECOVERY_BUNDLE_V3.md`, `FRESH_V3_HOSTED_RESTORE_20260827.md`, and `ROLLBACK.md`. Historical phase documents remain implementation evidence unless this runbook explicitly retains one of their checks.

## Safety boundary

- Run catalog/fingerprint checks read-only against the intended project unless a section explicitly names the disposable recovery target.
- Confirm the project ref before any mutating recovery acceptance SQL.
- Never run the synthetic cloud recovery acceptance against Production `avahcwyxparbcjdfglzx`.
- Do not apply migration/rollback SQL merely because a fingerprint differs.
- Do not broaden `anon`, `authenticated`, `service_role`, table, sequence, Vault, or RLS privileges to make a restored application work.
- Do not select or decrypt customer Vault secret values for verification.
- A fingerprint mismatch is an investigation trigger, not authorization to repair Production.

## 1. Migration ledger and future-object boundary

Current Production migration authority is the consolidated `P0_MIGRATION_LEDGER.md`; `P0_MIGRATION_LEDGER_20260825_APPENDIX.md` remains point-in-time historical evidence.

Accepted Production migration count: `51`.

Accepted head:

`20260825075808 / post_p5_rate_limit_concurrency`

Preceding accepted future-object migration:

`20260825040850 / post_p5_public_default_privilege_guard`

This is the accepted **future-object default-privilege hardening** boundary for postgres-created objects in `public`. Historical 2026-08-13/14 SQL gaps remain unresolved; do not reconstruct missing historical SQL by guessing from the live schema.

Recovery Bundle v3 carries a safe `migration-ledger.sql` generated from Production `version/name` fields only. It intentionally excludes historical `statements` / `rollback` arrays.

## 2. Primary CRM catalog/security fingerprint

Run:

`supabase/baseline/p0_schema_security_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 200`
- `crm_schema_security_sha256 = 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`

This covers the retained `crm_*` catalog/security contract, including function definitions, effective application-role EXECUTE truth, direct application-role table grants, RLS flags, policies, constraints, indexes, and triggers.

## 3. Post-P5 guard fingerprint and database-level event triggers

Run:

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`

Accepted Production checkpoint:

- `guard_inventory_lines = 9`
- `guard_security_sha256 = 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`

The three repository-managed GrowthOps DDL guards are:

- `growthops_crm_acl_guard_ddl`
- `growthops_crm_rls_guard_ddl`
- `growthops_public_noncrm_function_acl_guard_ddl`

The accepted hosted state contains four enabled database-level event triggers with public handlers:

- `ensure_rls` → `public.rls_auto_enable()`
- `growthops_crm_acl_guard_ddl` → `public.growthops_crm_acl_guard_ddl()`
- `growthops_crm_rls_guard_ddl` → `public.growthops_crm_rls_guard_ddl()`
- `growthops_public_noncrm_function_acl_guard_ddl` → `public.growthops_public_noncrm_function_acl_guard_ddl()`

The first real `schema.sql` omitted these database-global trigger objects; Recovery Bundle v3 carries `event-triggers.sql` to restore them after their handler functions exist.

## 4. Wider public-schema recovery fingerprint

Run:

`supabase/baseline/p0_public_schema_recovery_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 225`
- `public_recovery_sha256 = a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`

This is a catalog-only supplemental recovery comparison. Extension-version changes can legitimately alter it, so a mismatch requires investigation rather than automatic rollback.

## 5. Current accepted security invariants

Current Production invariants include:

- CRM RLS enabled on `9 / 9` CRM business tables;
- browser-facing CRM policies: `0` under the RPC-only/default-deny design;
- effective CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`;
- direct CRM table grants for those application roles: `0 / 0 / 0`;
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`;
- existing non-CRM public functions/procedures executable by an application role: `0`.

Production Vault count remains an integrity signal only. Do not inspect customer secret values to explain a count difference.

## 6. Migration-specific retained checks

For the current rate-limit concurrency boundary retain:

- `supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql`
- `supabase/baseline/post_p5_rate_limit_concurrency_check.sql`
- `test_post_p5_rate_limit_concurrency.py`

For the retained future-object default-privilege boundary retain:

- `supabase/baseline/post_p5_public_default_privilege_guard_check.sql`
- `supabase/baseline/post_p5_public_default_privilege_guard_probe.sql`
- `test_post_p5_public_default_privilege_guard.py`

The future-object probe remains transaction-contained, must never COMMIT, and must prove its synthetic objects rolled back.

## 7. Application/runtime boundary evidence

Historical PR #86 Vercel Git deployment-policy acceptance remains valid evidence:

- `main@91c0edcb24b79d282faa72d7d83435a1e1265d30`
- CRM Build Gate #77: completed / success
- Vercel Production `dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6`: `READY`

The independently revalidated Vercel runtime/security checkpoint after restoring the Production-only server identity is `dpl_JWXVvjCdjRF59gMrZycDUJEXYP7G` on `main@e77e9232c737015132b390c4d1de549c19ce1761`; recent `/api/crm` logs included successful 200 responses with no new `server_identity_missing` event. Later documentation/recovery-control commits do not automatically supersede that runtime checkpoint.

The last independently verified Cloudflare Production runtime-compatible deployment remains `49a23f7f-5fbe-4894-9b8e-ad7b25005d70 / main@0eefbe3`.

After a real application recovery, also require the canonical repository gate, intended deployment-to-commit mapping, safe unauthenticated `GET /api/crm` rejection, a safe public RPC through the BFF, and runtime-error inspection before declaring the application recovered.

## 8. Preview Production-secret isolation

Recovery acceptance does not authorize Preview to use Production Supabase.

Historical fail-closed evidence is retained: Vercel Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` reached `sh build.sh` on 2026-08-25 and failed with `PREVIEW_SECRET_BOUNDARY_FAILED`. No secret value was printed. PR #86 then retained the main-only Git deployment policy.

**Preview Production-secret cleanup accepted on 2026-08-27.** Independent evidence records:

- `Vercel Preview: no project environment variables`; Production retains its hidden server secret scoped to Production only;
- `Cloudflare Preview: `GROWTHOPS_SUPABASE_SECRET_KEY` removed`; Cloudflare Production retains its encrypted Production binding;
- Issue #92: closed / completed.

Historical open-state evidence remains audit history and must not be interpreted as the current platform state.

## 9. Accepted Recovery Bundle v3 artifact

The first authorized schema-only export (run `32983830368`) remains historical evidence. It proved a real dump could be created but omitted database-level event-trigger objects and the migration ledger.

The current accepted portable recovery artifact is Recovery Bundle v3 from workflow run `33079493119`, generated from protected:

`main@89e1904a521c41ab1b35eb29ef25c2834bf76538`

Accepted artifact evidence:

- `growthops-schema-recovery-bundle-v3-33079493119`
- artifact ID `9649406110`
- ZIP SHA-256 `c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7`
- 12 files / 22,424 bytes
- `schema.sql` 100,993 bytes / SHA-256 `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`
- exactly four event-trigger restore statements
- exactly 51 safe migration `version/name` entries
- `post-schema-security.sql` with exactly 12 CRM `service_role EXECUTE` grants, no `anon`/`authenticated` grants, and no `supabase_admin` default-ACL changes
- internal `recovery-files.sha256` manifest independently verified
- metadata excludes customer rows and migration statement arrays.

Recovery Bundle v3 restore order is:

1. `schema.sql`
2. `event-triggers.sql`
3. `post-schema-security.sql`
4. `migration-ledger.sql`

`post-schema-security.sql` is the accepted fresh-project postgres/public ACL reconciliation. It must not be replaced with broad privilege restoration.

## 10. Fresh hosted v3 restore proof

The second truly fresh disposable hosted recovery target is:

`qczkskuaszlezlcxxpqk / growthops-recovery-bundle-v3-test / ap-southeast-1`

Its application start was proven empty before restore:

- public tables `0`
- public routines `0`
- public event triggers `0`
- application migration table absent.

After the accepted v3 restore, the target matched:

- primary `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`
- guard `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`
- wider-public `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`
- migration count `51`, head `20260825075808 / post_p5_rate_limit_concurrency`
- RLS `9 / 9`
- CRM EXECUTE `0 / 0 / 12`
- four expected database-level event triggers.

A transaction-contained future-object probe passed for a synthetic CRM table, sequence, CRM function, and non-CRM public function. RLS/default-deny behavior held, the transaction rolled back, and all probe objects were proven absent.

After catalog/future-object verification the disposable target remained clean: `crm_users=0`, `crm_workspaces=0`, `crm_sessions=0`, `crm_server_audit_logs=0`, and `vault.secrets=0`.

Security Advisor reported only expected `RLS enabled / no policy` INFO notices; Performance Advisor reported only unused-index INFO notices expected on a no-traffic recovery database. These notices do not authorize schema changes.

Detailed evidence is in `FRESH_V3_HOSTED_RESTORE_20260827.md`.

### Transport audit disclosure

Because the connected SQL transport could not send the approximately 100 KB `schema.sql` in one payload, it was transported in statement-boundary batches. One batch introduced an obsolete unused `k text;` declaration into `crm_role_view_state`. Direct ZIP inspection proved the accepted artifact did **not** contain that declaration. The disposable target was corrected only by re-applying the exact original bundled function definition, then deleting the transport-only migration record. This was an executor transcription correction, not a Bundle v3 or Production repair.

## 11. Final #93 closure condition — synthetic cloud acceptance

Issue #93 remains open for one substantive acceptance step only.

The canonical psql script is:

`supabase/baseline/p0_cloud_recovery_acceptance.sql`

The connected SQL execution safety layer blocks its credential/reveal payload before it reaches Postgres, so **it has not yet been executed successfully in this recovery run**.

For Supabase SQL Editor, use the Gate-pinned equivalent:

`supabase/baseline/p0_cloud_recovery_acceptance_sql_editor.sql`

It removes only the psql-only `\set ON_ERROR_STOP on` compatibility line, retains the canonical `BEGIN` / assertion body / `ROLLBACK`, contains no `COMMIT`, and adds one explicit success-row SELECT only after rollback.

Run it only on the disposable target `qczkskuaszlezlcxxpqk`, never Production. Require the visible result:

`P0_CLOUD_RECOVERY_ACCEPTANCE_OK`

Then immediately run the read-only/count-only:

`supabase/baseline/p0_cloud_recovery_acceptance_postcheck.sql`

Require:

- `crm_users = 0`
- `crm_workspaces = 0`
- `crm_sessions = 0`
- `crm_server_audit_logs = 0`
- `vault_secret_rows = 0`
- `rollback_clean = true`

After those two checks pass, independently re-run the 51-entry migration head plus primary/guard/wider-public fingerprints. Only then update this runbook to accepted/closed, close #93, and finalize the disposable-project lifecycle.

## 12. Record a new accepted checkpoint when state intentionally changes

After a legitimate Production schema/ACL/function/guard migration, update the migration mapping, relevant fingerprints, `CURRENT_STATE.md`, and this runbook from fresh read-only Production evidence. Preserve historical checkpoint documents rather than rewriting their old values.
