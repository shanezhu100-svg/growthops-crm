# Full Schema Export Recovery Procedure

Last reviewed: 2026-08-27

This runbook defines the trusted path for the outstanding P0 **portable schema recovery** deliverable. It complements, but does not replace, the deterministic comparison checks in `CURRENT_RECOVERY_VERIFICATION.md`.

## Current status

A real authorized Production schema-only export **has been produced and independently checksum-verified**, but zero-to-current recovery is **not yet accepted**.

The first successful export was generated from protected `main@e77e9232c737015132b390c4d1de549c19ce1761` by GitHub Actions workflow run `32983830368` using Supabase CLI `2.116.0` against canonical Production project `avahcwyxparbcjdfglzx`.

First-artifact evidence:

- artifact name: `growthops-schema-only-32983830368`;
- `schema.sql` size: `100993` bytes;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`;
- temporary GitHub ZIP digest: `189e165d4c6e86352d239d79a89f51bb845cc06108fbe5bbd46b9e21b3d994c7`;
- a private operator copy was saved outside the temporary 7-day GitHub artifact.

The first artifact is useful and must be retained, but a completeness review found two recovery gaps that prevent it from being treated as a self-sufficient zero-to-current bundle:

1. the filtered Supabase schema dump contains the four public event-trigger **handler functions** but contains **zero `CREATE EVENT TRIGGER` objects**;
2. the dump contains no `supabase_migrations.schema_migrations` history, while Supabase's restore guidance treats migration-history preservation as a separate step.

Production currently has four enabled postgres-owned event triggers whose handlers are in `public`:

- `ensure_rls` → `public.rls_auto_enable()`;
- `growthops_crm_acl_guard_ddl` → `public.growthops_crm_acl_guard_ddl()`;
- `growthops_crm_rls_guard_ddl` → `public.growthops_crm_rls_guard_ddl()`;
- `growthops_public_noncrm_function_acl_guard_ddl` → `public.growthops_public_noncrm_function_acl_guard_ddl()`.

The three GrowthOps guard bindings are part of the accepted supplemental guard fingerprint. A restore that contains the handler functions but not the event-trigger objects is therefore not security-equivalent to Production.

## Recovery bundle v2

The protected manual recovery workflow is being hardened to generate a **schema recovery bundle** rather than treating `schema.sql` alone as complete. The bundle contains no customer rows and no Vault plaintext.

Required bundle files:

- `schema.sql` — authoritative Supabase CLI filtered schema dump;
- `event-triggers.sql` — database-level event-trigger recovery adjunct generated from the authorized Production catalog;
- `event-trigger-inventory.txt` — safe event-trigger event/enabled/tag/handler/owner inventory;
- `migration-ledger.txt` — safe `version|name` migration ledger;
- `migration-ledger.sql` — recovery-only `version/name` ledger reconstruction for a new isolated Supabase target;
- `recovery-files.sha256` — checksum manifest for the bundle;
- `recovery-metadata.txt` — project ref, tool versions, source commit, counts, heads, and checksums;
- tool-version files.

The workflow must fail closed unless all four expected event-trigger names are present, all are enabled in normal/origin mode, all are postgres-owned, the migration ledger has exactly `51` entries, and its head is `20260825075808 / post_p5_rate_limit_concurrency`.

The safe migration-ledger artifacts intentionally exclude the `statements` and `rollback` arrays from `supabase_migrations.schema_migrations`. Those historical SQL arrays are not required to prove the current schema/security state and are not uploaded to the public-repository-associated temporary artifact without a separate sensitivity review. The safe ledger preserves the applied `version/name` authority used for current recovery-head verification; it is **not** a forensic copy of every historical migration statement.

## Credential safety rules

- Never commit the database password or complete credential-bearing connection string to GitHub.
- Never paste the password into issue/PR descriptions, build logs, screenshots, chat transcripts, Pages/Vercel logs, or normal CRM backups.
- A service-role/API secret is **not** a PostgreSQL database password and must never be substituted into a Postgres connection string.
- The workflow may reference the encrypted `SUPABASE_DB_URL` repository secret but must mask it and never print it.
- Do not export customer table rows or Vault plaintext as part of this schema-recovery deliverable.
- Do not commit generated `schema.sql`, recovery SQL artifacts, or connection material to this public repository.

## Restore verification target

A bundle existing on disk is not enough. The final acceptance must use a **new, isolated, disposable Supabase project** that has never previously been modified to mirror Production.

The existing `growthops-p0-recovery-test` project is useful for historical testing but already contains CRM schema and therefore is not accepted as proof of a from-zero restore.

For a new hosted Supabase recovery target, use this order:

1. confirm the target is the disposable recovery project and **not Production**;
2. restore `schema.sql` with `psql --single-transaction --variable ON_ERROR_STOP=1` using the new project's authorized database connection;
3. restore `event-triggers.sql` after the handler functions exist;
4. apply `migration-ledger.sql` only to the disposable recovery project so its safe version/name ledger reflects the accepted Production migration head;
5. run the read-only checks in `CURRENT_RECOVERY_VERIFICATION.md`;
6. require the primary, three-guard, and wider-public fingerprints to match the accepted checkpoint unless a reviewed platform-only difference is explicitly understood;
7. run `supabase/baseline/p0_cloud_recovery_acceptance.sql` only on the empty disposable recovery project; its synthetic test data must remain transaction-contained and rolled back;
8. verify the application/recovery boundary without introducing Production secrets into Preview or the recovery target;
9. pause/delete the disposable target after evidence is captured according to the approved recovery-test lifecycle.

Never run the synthetic cloud recovery acceptance script against Production.

## Current comparison checkpoints

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- supplemental CRM guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- supplemental wider-public recovery fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- accepted Production migration head: `20260825075808 / post_p5_rate_limit_concurrency`.

The known 2026-08-13/14 migration-history gap remains relevant: repository migrations alone must not be presented as a zero-to-current replacement for the portable Production schema snapshot.

## What does not count as completion

None of the following closes the recovery deliverable by itself:

- fingerprints or catalog inventories without a portable dump;
- the first `schema.sql` artifact without its missing database-level event-trigger bindings;
- repository migration files alone while the known 2026-08-13/14 migration-history gap remains;
- a generated catalog/DDL manifest used **instead of** the Supabase CLI schema dump;
- restoring into a project that already contains the CRM schema;
- a successful restore that does not reproduce the three accepted fingerprints/security boundaries;
- a Production dashboard screenshot;
- a data backup whose schema/security contents have not been independently verified.

The event-trigger adjunct is not a substitute for the dump: it is a narrowly scoped supplement for database-global security objects that the reviewed filtered schema artifact omitted.

## Closure condition

Issue #93 remains open until a freshly generated recovery bundle v2 is independently checksum-inspected, restored into a truly empty disposable Supabase target, and passes `CURRENT_RECOVERY_VERIFICATION.md` plus the synthetic recovery acceptance restricted to that target.
