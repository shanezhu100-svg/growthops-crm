# Current CRM Recovery Verification

Last reviewed: 2026-08-25

This is the current read-only verification entrypoint for GrowthOps CRM recovery and database-change rollback acceptance. It does **not** replace a full schema backup and it does **not** authorize automatic database repair.

Use this runbook with `CURRENT_STATE.md` and `ROLLBACK.md`. Older P0/P5/Post-P5 documents remain historical implementation evidence unless this runbook explicitly names one of their retained read-only SQL files.

## Safety boundary

- Run the checks below read-only against the intended Supabase project.
- Confirm the target project before executing any SQL.
- Do not run migration or rollback SQL merely because a fingerprint differs.
- Do not broaden `anon`, `authenticated`, `service_role`, table, sequence, Vault, or RLS privileges to make a restored application work.
- Do not select or decrypt customer Vault secret values for verification.
- `supabase/baseline/p0_cloud_recovery_acceptance.sql` is **not** a Production check. It creates synthetic test data inside a transaction and is restricted to an empty disposable isolated recovery project.
- `supabase/baseline/post_p5_public_default_privilege_guard_probe.sql` is a reviewed Production acceptance probe that creates named synthetic objects only inside one explicit transaction, asserts their future-object ACL behavior, rolls the transaction back, and then proves all probe objects are absent. Do not remove its rollback/no-COMMIT safety checks.

## 1. Confirm the migration ledger

Run the ledger section of:

`supabase/baseline/p0_recovery_inventory.sql`

Compare the result with `P0_MIGRATION_LEDGER.md`, `P0_MIGRATION_LEDGER_20260825_APPENDIX.md`, and the current repository migration mapping. Historical 2026-08-13/14 SQL gaps remain unresolved; do not reconstruct them by guessing from the live schema.

For the accepted 2026-08-25 Production checkpoint, the latest recorded migration is:

`20260825075808 / post_p5_rate_limit_concurrency`

The preceding accepted future-object migration remains:

`20260825040850 / post_p5_public_default_privilege_guard`

A newer legitimate migration requires updating the current checkpoints after its reviewed Production acceptance.

## 2. Recompute the primary CRM catalog/security fingerprint

Run:

`supabase/baseline/p0_schema_security_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 200`
- `crm_schema_security_sha256 = 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`

This fingerprint covers the retained `crm_*` catalog/security contract, including CRM columns, constraints, indexes, table triggers, `crm_*` function definitions and effective application-role EXECUTE truth, direct application-role table grants, RLS flags, and policies.

The primary fingerprint changed from the preceding `200 / bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1` checkpoint because `post_p5_rate_limit_concurrency` intentionally replaced the definitions of `crm_login`, `crm_unlock_credentials_v1`, and `crm_reveal_client_secret_value_v5`. That older hash remains historical evidence for the pre-concurrency definitions and is no longer the current Production comparison anchor.

The future-object default-privilege hardening remains outside the historical `crm_*` namespace and is represented separately by the supplemental guard fingerprint below.

If the primary fingerprint differs unexpectedly, stop and identify the exact catalog/ACL/function change before using any rollback artifact.

## 3. Recompute the Post-P5 guard fingerprint

Run:

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`

Accepted Production checkpoint:

- `guard_inventory_lines = 9`
- `guard_security_sha256 = 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`

This supplemental fingerprint covers the three repository-managed DDL security guards that sit outside the historical `crm_*` function namespace:

- `growthops_crm_acl_guard_ddl`
- `growthops_crm_rls_guard_ddl`
- `growthops_public_noncrm_function_acl_guard_ddl`

It includes their complete function definitions/owners, effective `anon` / `authenticated` / `service_role` EXECUTE truth, and event-trigger event/enabled/tags/function bindings.

The third guard is intentionally public-only and non-`crm_*`: it closes future function/procedure EXECUTE exposure while leaving Supabase platform schemas outside GrowthOps ownership.

Do not extend this checkpoint by guessing ownership of unrelated Supabase/platform or historical event triggers.

## 4. Run the retained data-safety/access inventory

Run the remaining read-only sections of:

`supabase/baseline/p0_recovery_inventory.sql`

Interpret them against **current** `CURRENT_STATE.md`, not the old P0 privilege phase. Current accepted Production invariants include:

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

## 5. Re-run migration-specific post-checks when a database rollback/change occurred

If recovery included a reviewed database migration or rollback, run the exact retained read-only preflight/post-check package for that control in `supabase/baseline/` and verify its corresponding canonical repository gate remains green.

For the current rate-limit concurrency boundary, run:

- `supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql` before a reviewed re-application or compatibility investigation;
- `supabase/baseline/post_p5_rate_limit_concurrency_check.sql` after an accepted apply/rollback verification;
- `test_post_p5_rate_limit_concurrency.py` through the canonical build gate to verify the migration/rollback/BFF contract remains intact.

The current Production state requires transaction-level advisory-lock serialization for the reviewed login trusted-source/user, credential-unlock workspace/user, and credential-reveal workspace/user subjects while preserving the existing thresholds. Unlock invalid/throttled and reveal throttled outcomes that require durable rejection auditing are returned as the reviewed committable envelopes and translated by both BFFs to the established safe HTTP contract.

For the retained future-object boundary, run:

- `supabase/baseline/post_p5_public_default_privilege_guard_check.sql` for the read-only catalog/default-ACL verification;
- the transaction-contained `supabase/baseline/post_p5_public_default_privilege_guard_probe.sql` only when a real future-object behavior acceptance check is warranted.

The accepted Production probe created a synthetic non-CRM function, table, and sequence, found no prohibited application-role/default exposure, rolled back, and confirmed all three probe objects absent.

Do not substitute a broad privilege restoration for a failed migration-specific post-check.

Current high-level boundaries that must remain true include:

- `anon` CRM RPC EXECUTE remains `0`;
- service-role CRM RPC entry surface remains the reviewed `12` functions (`11` BFF entries plus server-only bootstrap);
- direct service-role CRM table and sequence grants remain `0`;
- future postgres-created public objects do not silently regain broad service-role/default function exposure;
- browser roles cannot execute broad/internal credential reveal paths;
- login/unlock/reveal concurrency serialization and reviewed committable rejection-audit semantics remain compatible with the selected application build;
- session, workspace-secret, login-source, ACL, RLS, and future-object guards remain intact.

## 6. Verify the application boundary after recovery

For the selected gate-accepted application commit:

1. run the canonical repository gate: `sh build.sh && python3 cloudflare_p1_verify.py`;
2. require final `CLOUDFLARE_P1_OUTPUT_PARITY_OK`;
3. verify the target Production deployment maps to the intended `main` commit and is healthy;
4. verify the canonical homepage loads the current server-boundary authentication copy;
5. verify unauthenticated `GET /api/crm` is rejected safely (`METHOD_NOT_ALLOWED`) rather than executing an RPC;
6. inspect Production runtime/deployment errors before declaring recovery complete.

The runtime/database concurrency acceptance evidence remains merged `main@0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6`, CRM Build Gate #69, Vercel Production `dpl_FNtV2oBQWPYZrm8BaShVybUm57fF` (`READY`), and Cloudflare Pages Production `49a23f7f-5fbe-4894-9b8e-ad7b25005d70` (`success`).

The current validated Vercel hosting/recovery checkpoint after later documentation and deployment-policy hardening is:

- `main@91c0edcb24b79d282faa72d7d83435a1e1265d30`;
- CRM Build Gate #77: completed / success;
- Vercel Production `dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6`: `READY`;
- stable alias `https://growthops-crm.vercel.app` assigned;
- homepage fetch succeeded;
- unauthenticated `GET /api/crm` returned `405 / METHOD_NOT_ALLOWED`, `Allow: POST`, no-store cache policy, and security headers;
- no new Production runtime-error cluster was observed in the checked recent window.

The last independently verified Cloudflare Production remains `49a23f7f-5fbe-4894-9b8e-ad7b25005d70 / main@0eefbe3`, which is runtime-compatible with the current database. A later docs-only `main@5172508` deployment was skipped because a newer deployment had already been queued. Exact Cloudflare deployment freshness after that point must be reverified through Cloudflare evidence; do not infer it from Vercel or GitHub state.

If credentials are available for an authorized smoke test, follow the functional checks in `ROLLBACK.md` without exposing password/2FA values in logs or screenshots.

## 7. Record the new accepted checkpoint when state intentionally changes

After a legitimate schema/ACL/function/guard migration is applied and verified, update the relevant current fingerprints, this runbook, `CURRENT_STATE.md`, and migration mapping from fresh read-only Production evidence. Preserve historical checkpoint documents rather than rewriting their old values.

For a function-definition change inside the primary `crm_*` fingerprint scope, explicitly recompute the primary hash even when the table/schema shape did not change.

## Preview isolation remains a separate platform check

Recovery acceptance does not authorize Preview to use Production Supabase. If a Preview environment has a server secret, it must either use an explicit isolated staging `GROWTHOPS_SUPABASE_URL` and matching staging secret or fail closed/remove the Preview secret. Do not weaken the origin guard for recovery convenience.

At the 2026-08-25 review, **both platform Preview secret scopes were confirmed as still requiring cleanup**:

- Cloudflare Preview had a `GROWTHOPS_SUPABASE_SECRET_KEY` binding without an accepted isolated staging URL; the guard correctly prevented a usable Preview backend. No secret value is recorded here.
- Vercel Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` reached `sh build.sh` and failed with `PREVIEW_SECRET_BOUNDARY_FAILED` because a server secret was present without an explicit staging Supabase URL. No secret value was printed or recorded.

Vercel normal non-main Git Preview execution was then hardened by PR #86 using `"**": false` plus exact `"main": true`. Its slash-containing PR branch produced no new Vercel Preview deployment during acceptance; CRM Build Gate #76 and merged-main Gate #77 both passed, and Vercel Production remained healthy. This is a mitigation of the normal Git execution path, not proof that the Preview-scoped secret has been deleted. Complete platform acceptance still requires removing the Production secret from Preview scope or configuring a truly isolated staging backend on each provider.

## Full schema portability remains separate

The two deterministic fingerprints and the retained read-only inventory are comparison/acceptance controls. They are **not** a complete schema export.

A trusted full schema-only `pg_dump`/equivalent snapshot remains an outstanding P0 recovery deliverable. Until that artifact exists, do not claim that the repository alone can recreate every historical database object from zero, especially the known 2026-08-13/14 migration gap.
