# Current CRM Recovery Verification

Last reviewed: 2026-08-24

This is the current read-only verification entrypoint for GrowthOps CRM recovery and database-change rollback acceptance. It does **not** replace a full schema backup and it does **not** authorize automatic database repair.

Use this runbook with `CURRENT_STATE.md` and `ROLLBACK.md`. Older P0/P5/Post-P5 documents remain historical implementation evidence unless this runbook explicitly names one of their retained read-only SQL files.

## Safety boundary

- Run the checks below read-only against the intended Supabase project.
- Confirm the target project before executing any SQL.
- Do not run migration or rollback SQL merely because a fingerprint differs.
- Do not broaden `anon`, `authenticated`, `service_role`, table, sequence, Vault, or RLS privileges to make a restored application work.
- Do not select or decrypt customer Vault secret values for verification.
- `supabase/baseline/p0_cloud_recovery_acceptance.sql` is **not** a Production check. It creates synthetic test data inside a transaction and is restricted to an empty disposable isolated recovery project.

## 1. Confirm the migration ledger

Run the ledger section of:

`supabase/baseline/p0_recovery_inventory.sql`

Compare the result with `P0_MIGRATION_LEDGER.md` and the current repository migration mapping. Historical 2026-08-13/14 SQL gaps remain unresolved; do not reconstruct them by guessing from the live schema.

For the accepted 2026-08-24 Production checkpoint, the latest recorded migration is:

`20260824034405 / post_p5_user_identity_byte_caps`

A newer legitimate migration requires updating the current checkpoints after its reviewed Production acceptance.

## 2. Recompute the primary CRM catalog/security fingerprint

Run:

`supabase/baseline/p0_schema_security_fingerprint.sql`

Accepted Production checkpoint:

- `inventory_lines = 200`
- `crm_schema_security_sha256 = bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1`

This fingerprint covers the retained `crm_*` catalog/security contract, including CRM columns, constraints, indexes, table triggers, `crm_*` function definitions and effective application-role EXECUTE truth, direct application-role table grants, RLS flags, and policies.

If it differs unexpectedly, stop and identify the exact catalog/ACL/function change before using any rollback artifact.

## 3. Recompute the Post-P5 guard fingerprint

Run:

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`

Accepted Production checkpoint:

- `guard_inventory_lines = 6`
- `guard_security_sha256 = d3491022f0827324c810d401123d6027c0c3d46498868a2b5520bbea54bae52f`

This supplemental fingerprint covers the two repository-managed DDL security guards that sit outside the historical `crm_*` function namespace:

- `growthops_crm_acl_guard_ddl`
- `growthops_crm_rls_guard_ddl`

It includes their complete function definitions/owners, effective `anon` / `authenticated` / `service_role` EXECUTE truth, and event-trigger event/enabled/tags/function bindings.

Do not extend this checkpoint by guessing ownership of unrelated Supabase/platform or historical event triggers.

## 4. Run the retained data-safety/access inventory

Run the remaining read-only sections of:

`supabase/baseline/p0_recovery_inventory.sql`

Interpret them against **current** `CURRENT_STATE.md`, not the old P0 privilege phase. Current accepted Production invariants include:

- CRM RLS enabled on `9 / 9` CRM business tables;
- browser-facing CRM policies: `0` under the current RPC-only/default-deny design;
- CRM RPC EXECUTE for `anon / authenticated / service_role`: `0 / 0 / 12`;
- direct CRM table grants for those application roles: `0 / 0 / 0`;
- current Vault secret row count: `1` unless a reviewed credential-model change intentionally changes it;
- ordinary workspace sensitive-key matches: `0`;
- server audit sensitive-payload-value matches: `0`.

The Vault count is an integrity signal only. Do not inspect customer secret values to explain a count difference.

## 5. Re-run migration-specific post-checks when a database rollback/change occurred

If recovery included a reviewed database migration or rollback, run the exact retained read-only preflight/post-check package for that control in `supabase/baseline/` and verify its corresponding canonical repository gate remains green.

Do not substitute a broad privilege restoration for a failed migration-specific post-check.

Current high-level boundaries that must remain true include:

- `anon` CRM RPC EXECUTE remains `0`;
- service-role CRM RPC entry surface remains the reviewed `12` functions (`11` BFF entries plus server-only bootstrap);
- direct service-role CRM table and sequence grants remain `0`;
- browser roles cannot execute broad/internal credential reveal paths;
- session, workspace-secret, login-source, ACL and RLS guard controls remain intact.

## 6. Verify the application boundary after recovery

For the selected gate-accepted application commit:

1. run the canonical repository gate: `sh build.sh && python3 cloudflare_p1_verify.py`;
2. require final `CLOUDFLARE_P1_OUTPUT_PARITY_OK`;
3. verify the target Production deployment maps to the intended `main` commit and is healthy;
4. verify the canonical homepage loads the current server-boundary authentication copy;
5. verify unauthenticated `GET /api/crm` is rejected safely (`METHOD_NOT_ALLOWED`) rather than executing an RPC;
6. inspect Production runtime/deployment errors before declaring recovery complete.

If credentials are available for an authorized smoke test, follow the functional checks in `ROLLBACK.md` without exposing password/2FA values in logs or screenshots.

## 7. Record the new accepted checkpoint when state intentionally changes

After a legitimate schema/ACL/function/guard migration is applied and verified, update the relevant current fingerprints and `CURRENT_STATE.md` from fresh read-only Production evidence. Preserve historical checkpoint documents rather than rewriting their old values.

## Full schema portability remains separate

The two deterministic fingerprints and the retained read-only inventory are comparison/acceptance controls. They are **not** a complete schema export.

A trusted full schema-only `pg_dump`/equivalent snapshot remains an outstanding P0 recovery deliverable. Until that artifact exists, do not claim that the repository alone can recreate every historical database object from zero, especially the known 2026-08-13/14 migration gap.
