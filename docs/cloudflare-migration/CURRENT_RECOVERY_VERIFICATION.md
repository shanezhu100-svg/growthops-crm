# Current CRM Recovery Verification

Last reviewed: 2026-08-27

This is the current read-only verification entrypoint for GrowthOps CRM recovery and database-change rollback acceptance. A real Production schema-only dump now exists, but the first dump was not complete enough to prove zero-to-current recovery by itself; recovery bundle v2 and a truly empty disposable-target restore remain required. This runbook does **not** authorize automatic database repair.

Use this runbook with `CURRENT_STATE.md`, `FULL_SCHEMA_EXPORT.md`, and `ROLLBACK.md`. Older P0/P5/Post-P5 documents remain historical implementation evidence unless this runbook explicitly names one of their retained read-only SQL files.

## Safety boundary

- Run the checks below read-only against the intended Supabase project unless a section explicitly identifies a disposable recovery target.
- Confirm the target project before executing any SQL.
- Never run the synthetic recovery acceptance script against Production.
- Do not run migration or rollback SQL merely because a fingerprint differs.
- Do not broaden `anon`, `authenticated`, `service_role`, table, sequence, Vault, or RLS privileges to make a restored application work.
- Do not select or decrypt customer Vault secret values for verification.
- `supabase/baseline/p0_cloud_recovery_acceptance.sql` is **not** a Production check. It creates synthetic test data inside a transaction and is restricted to an empty disposable isolated recovery project.
- `supabase/baseline/post_p5_public_default_privilege_guard_probe.sql` is a reviewed Production acceptance probe that creates named synthetic objects only inside one explicit transaction, asserts their future-object ACL behavior, rolls the transaction back, and then proves all probe objects are absent. Do not remove its rollback/no-COMMIT safety checks.

## 1. Confirm the migration ledger

Run the ledger section of:

`supabase/baseline/p0_recovery_inventory.sql`

Compare the result with `P0_MIGRATION_LEDGER.md`, `P0_MIGRATION_LEDGER_20260825_APPENDIX.md`, and the current repository migration mapping. Historical 2026-08-13/14 SQL gaps remain unresolved; do not reconstruct them by guessing from the live schema.

Accepted Production head:

`20260825075808 / post_p5_rate_limit_concurrency`

Preceding accepted future-object migration:

`20260825040850 / post_p5_public_default_privilege_guard`

This migration is the accepted **future-object default-privilege hardening** boundary for postgres-created objects in `public`; its read-only check and transaction-contained probe remain part of recovery acceptance.

Production currently has 51 application migration ledger entries. A newer legitimate migration requires updating the current checkpoints after its reviewed Production acceptance.

For a **new disposable recovery target**, recovery bundle v2 includes `migration-ledger.sql`, generated from only the Production `version/name` fields. It intentionally excludes the historical `statements` and `rollback` arrays. Apply it only after `schema.sql` to reconstruct the safe version/name recovery ledger; it is not a forensic copy of every historical migration statement.

## 2. Recompute the primary CRM catalog/security fingerprint

Run:

`supabase/baseline/p0_schema_security_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 200`
- `crm_schema_security_sha256 = 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`

This fingerprint covers the retained `crm_*` catalog/security contract, including CRM columns, constraints, indexes, table triggers, `crm_*` function definitions and effective application-role EXECUTE truth, direct application-role table grants, RLS flags, and policies.

The primary fingerprint changed from the preceding `200 / bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1` checkpoint because `post_p5_rate_limit_concurrency` intentionally replaced three `crm_*` function definitions. That older hash remains historical evidence for the pre-concurrency definitions and is no longer the current Production comparison anchor.

If the primary fingerprint differs unexpectedly, stop and identify the exact catalog/ACL/function change before using any rollback artifact.

## 3. Recompute the Post-P5 guard fingerprint

Run:

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`

Accepted Production checkpoint:

- `guard_inventory_lines = 9`
- `guard_security_sha256 = 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`

This supplemental fingerprint covers the three repository-managed DDL security guards outside the historical `crm_*` function namespace:

- `growthops_crm_acl_guard_ddl`
- `growthops_crm_rls_guard_ddl`
- `growthops_public_noncrm_function_acl_guard_ddl`

It includes their complete function definitions/owners, effective `anon` / `authenticated` / `service_role` EXECUTE truth, and event-trigger event/enabled/tags/function bindings.

A 2026-08-27 completeness review of the first real `schema.sql` found all four public event-trigger handler functions but zero `CREATE EVENT TRIGGER` objects. A live read-only Production catalog check confirmed four enabled postgres-owned event triggers with public handlers:

- `ensure_rls` → `public.rls_auto_enable()`;
- `growthops_crm_acl_guard_ddl` → `public.growthops_crm_acl_guard_ddl()`;
- `growthops_crm_rls_guard_ddl` → `public.growthops_crm_rls_guard_ddl()`;
- `growthops_public_noncrm_function_acl_guard_ddl` → `public.growthops_public_noncrm_function_acl_guard_ddl()`.

Recovery bundle v2 therefore includes an exact `event-trigger-inventory.txt` and generated `event-triggers.sql` adjunct. On a disposable recovery target, restore `event-triggers.sql` only after `schema.sql` has restored the handler functions, then require this guard fingerprint to match.

## 4. Recompute the wider public-schema recovery fingerprint

Run:

`supabase/baseline/p0_public_schema_recovery_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 225`
- `public_recovery_sha256 = a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`

This supplemental read-only fingerprint broadens recovery comparison beyond the historical `crm_*` primary scope and the three GrowthOps guard functions. It hashes deterministic metadata for the `public` schema and relations, columns, constraints, indexes, user triggers, all public routine definitions/ACLs, application-role EXECUTE truth, policies, event triggers whose handler is in `public`, relevant default ACL rows, and installed extension metadata.

At the accepted checkpoint, a separate count inventory observed 9 public tables, 1 public sequence, 27 indexes, 30 constraints, 5 user triggers, 44 public routines, zero public policies, and four event triggers bound to public handler functions.

The query was executed twice consecutively against Production with the same `225 / a0078c5d...` result and matched again in later read-only verification. Extension-version changes can legitimately alter this wider fingerprint, so a difference is an investigation trigger rather than automatic rollback authorization. See `PUBLIC_SCHEMA_RECOVERY_FINGERPRINT.md`.

This fingerprint is comparison evidence only. It does not replace the portable recovery bundle or empty-target restore proof.

## 5. Re-run the retained data-safety/access inventory

Run the remaining read-only sections of:

`supabase/baseline/p0_recovery_inventory.sql`

Interpret them against **current** `CURRENT_STATE.md`, not an old privilege phase. Current accepted Production invariants include:

- CRM RLS enabled on `9 / 9` CRM business tables;
- browser-facing CRM policies: `0` under the current RPC-only/default-deny design;
- effective public function EXECUTE for `anon / authenticated / service_role`: `0 / 0 / 12`;
- direct CRM table grants for those application roles: `0 / 0 / 0`;
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`;
- existing non-CRM public functions/procedures executable by an application role: `0`;
- current Vault secret row count: `1` unless a reviewed credential-model change intentionally changes it;
- ordinary workspace sensitive-key matches: `0`;
- server audit sensitive-payload-value matches: `0`.

The Vault count is an integrity signal only. Do not inspect customer secret values to explain a count difference.

## 6. Re-run migration-specific post-checks when a database rollback/change occurred

If recovery included a reviewed database migration or rollback, run the exact retained read-only preflight/post-check package for that control in `supabase/baseline/` and verify its corresponding canonical repository gate remains green.

For the current rate-limit concurrency boundary, retain:

- `supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql` before a reviewed re-application or compatibility investigation;
- `supabase/baseline/post_p5_rate_limit_concurrency_check.sql` after an accepted apply/rollback verification;
- `test_post_p5_rate_limit_concurrency.py` through the canonical build gate to verify the migration/rollback/BFF contract remains intact.

The current Production state requires transaction-level advisory-lock serialization for the reviewed login trusted-source/user, credential-unlock workspace/user, and credential-reveal workspace/user subjects while preserving the existing thresholds. Unlock invalid/throttled and reveal throttled outcomes that require durable rejection auditing remain the reviewed committable envelopes translated by both BFFs to the established safe HTTP contract.

For the retained future-object boundary, run:

- `supabase/baseline/post_p5_public_default_privilege_guard_check.sql` for the read-only catalog/default-ACL verification;
- the transaction-contained `supabase/baseline/post_p5_public_default_privilege_guard_probe.sql` only when a real future-object behavior acceptance check is warranted.

Do not substitute a broad privilege restoration for a failed migration-specific post-check.

## 7. Verify the application boundary after recovery

For the selected gate-accepted application commit:

1. run the canonical repository gate: `sh build.sh && python3 cloudflare_p1_verify.py`;
2. require final `CLOUDFLARE_P1_OUTPUT_PARITY_OK`;
3. verify the target deployment maps to the intended gate-accepted commit and is healthy;
4. verify unauthenticated `GET /api/crm` is rejected safely (`METHOD_NOT_ALLOWED`) rather than executing an RPC;
5. verify a safe public RPC can reach Supabase through the BFF without exposing the server secret;
6. inspect runtime/deployment errors before declaring recovery complete.

Historical PR #86 Vercel Git deployment-policy acceptance remains valid evidence:

- `main@91c0edcb24b79d282faa72d7d83435a1e1265d30`;
- CRM Build Gate #77: completed / success;
- Vercel Production `dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6`: `READY`.

The latest independently revalidated Vercel runtime/security checkpoint after restoring the Production-only server identity is `dpl_JWXVvjCdjRF59gMrZycDUJEXYP7G` on `main@e77e9232c737015132b390c4d1de549c19ce1761`; merged-main Gate #98 passed and recent `/api/crm` runtime logs included successful 200 responses with no new `server_identity_missing` event. Later documentation/workflow-only main commits do not automatically supersede that runtime checkpoint.

The last independently verified Cloudflare Production runtime-compatible deployment remains `49a23f7f-5fbe-4894-9b8e-ad7b25005d70 / main@0eefbe3`; exact Cloudflare deployment-SHA freshness after later documentation/config-only commits remains a separate hosting evidence question.

## 8. Preview isolation is verified separately from recovery

Recovery acceptance does not authorize Preview to use Production Supabase. If a future Preview environment has a server secret, it must use an explicit isolated staging `GROWTHOPS_SUPABASE_URL` and matching staging secret or fail closed. Do not weaken the origin guard for recovery convenience.

Historical fail-closed evidence is retained: Vercel Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` reached `sh build.sh` on 2026-08-25 and failed with `PREVIEW_SECRET_BOUNDARY_FAILED` because a server secret was present without an explicit staging Supabase URL. No secret value was printed or recorded. PR #86 then disabled normal non-main Vercel Git deployments with `"**": false` plus exact `"main": true`.

**Preview Production-secret cleanup accepted on 2026-08-27.** Independent evidence now records:

- `Vercel Preview: no project environment variables`; Production retains hidden `GROWTHOPS_SUPABASE_SECRET_KEY` scoped to Production only;
- `Cloudflare Preview: `GROWTHOPS_SUPABASE_SECRET_KEY` removed`; Cloudflare Production retains its encrypted Production binding;
- Issue #92: closed / completed.

The historical open-state evidence remains audit history; it must not be interpreted as the current platform state.

## 9. Portable schema recovery bundle status

The first real authorized schema-only Production export was generated by workflow run `32983830368` from protected `main@e77e9232c737015132b390c4d1de549c19ce1761` using Supabase CLI `2.116.0`:

- artifact: `growthops-schema-only-32983830368`;
- `schema.sql` bytes: `100993`;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`;
- temporary ZIP SHA-256: `189e165d4c6e86352d239d79a89f51bb845cc06108fbe5bbd46b9e21b3d994c7`;
- a private operator copy was saved outside the temporary GitHub artifact.

That first artifact is retained but is not accepted as complete zero-to-current proof because the reviewed `schema.sql` omitted database-level event-trigger objects and the migration ledger.

PR #97 hardened the manual recovery workflow into bundle v2. Final PR Gate #100 passed, the PR squash-merged to protected `main@cfadbb42b31f11c6cce2843020d46f00ecac1dc1`, and merged-main Gate #101 passed. Bundle v2 keeps the authoritative Supabase CLI `schema.sql` and adds:

- exact `event-trigger-inventory.txt` and generated `event-triggers.sql`;
- safe `migration-ledger.txt` / `migration-ledger.sql` containing only version/name, not historical statement/rollback arrays;
- `recovery-files.sha256` and non-sensitive metadata;
- fail-closed assertions for exactly four expected enabled postgres-owned event triggers, exactly 51 migrations, and head `20260825075808 / post_p5_rate_limit_concurrency`;
- explicit metadata that customer rows and migration statement arrays are excluded and empty-target restore remains required.

A fresh bundle-v2 artifact has not yet been accepted until the updated manual workflow is dispatched from protected main and its files/checksums are independently inspected.

## 10. Empty-target restore closure condition

The existing `growthops-p0-recovery-test` project already contains CRM schema and therefore cannot prove a from-zero restore. Final #93 acceptance requires a **new, isolated, disposable Supabase project**.

Restore order for that target:

1. confirm the target is disposable recovery and not Production;
2. restore `schema.sql`;
3. restore `event-triggers.sql` after handler functions exist;
4. apply `migration-ledger.sql` only to the disposable target;
5. run sections 1–7 above and require the accepted primary / guard / wider-public checkpoints;
6. run `supabase/baseline/p0_cloud_recovery_acceptance.sql` only on the empty disposable target and require its synthetic transaction to roll back;
7. capture non-sensitive verification evidence, then pause/delete the disposable target according to the approved lifecycle.

Issue #93 remains open until a fresh bundle-v2 artifact is independently checksum-inspected, restored into that truly empty target, and passes the complete recovery acceptance. A fingerprint mismatch is an investigation trigger, not authorization to repair Production.

## 11. Record a new accepted checkpoint when state intentionally changes

After a legitimate schema/ACL/function/guard migration is applied and verified, update the relevant current fingerprints, this runbook, `CURRENT_STATE.md`, and migration mapping from fresh read-only Production evidence. Preserve historical checkpoint documents rather than rewriting their old values.

For a function-definition change inside the primary `crm_*` fingerprint scope, explicitly recompute the primary hash even when table/schema shape did not change. For any accepted public-schema/ACL/extension change, also recompute the wider public-schema recovery fingerprint.
