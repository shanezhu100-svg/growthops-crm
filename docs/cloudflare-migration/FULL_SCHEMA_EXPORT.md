# Full Schema Export Recovery Procedure

Last reviewed: 2026-08-27

This runbook defines the trusted portable-schema recovery path for canonical Production project `avahcwyxparbcjdfglzx`. It complements the deterministic comparison checks in `CURRENT_RECOVERY_VERIFICATION.md`; fingerprints are evidence, not a substitute for a real recovery artifact.

## Current status

A real authorized Production schema-only export **has been produced and independently checksum-verified**, but zero-to-current recovery is **not yet accepted**.

The first successful export was generated from protected `main@e77e9232c737015132b390c4d1de549c19ce1761` by GitHub Actions workflow run `32983830368` using Supabase CLI `2.116.0`.

First-artifact evidence:

- artifact: `growthops-schema-only-32983830368`;
- `schema.sql` size: `100993` bytes;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`;
- temporary ZIP SHA-256: `189e165d4c6e86352d239d79a89f51bb845cc06108fbe5bbd46b9e21b3d994c7`;
- a private operator copy was saved outside the temporary GitHub artifact.

The first artifact remains valid snapshot evidence, but review found **zero `CREATE EVENT TRIGGER` objects** even though the handler functions were present, and no `supabase_migrations.schema_migrations` ledger. Production has four enabled postgres-owned event triggers whose handlers are in `public`:

- `ensure_rls` → `public.rls_auto_enable()`;
- `growthops_crm_acl_guard_ddl` → `public.growthops_crm_acl_guard_ddl()`;
- `growthops_crm_rls_guard_ddl` → `public.growthops_crm_rls_guard_ddl()`;
- `growthops_public_noncrm_function_acl_guard_ddl` → `public.growthops_public_noncrm_function_acl_guard_ddl()`.

The safe migration recovery artifacts intentionally preserve only `version/name`; the historical `statements` and `rollback` arrays are excluded from the public-repository-associated artifact. The known 2026-08-13/14 migration-history gap remains relevant, so repository migrations alone must not be presented as a zero-to-current recovery substitute.

## Recovery Bundle v2 evidence

Recovery Bundle v2 added:

- `schema.sql`;
- `event-triggers.sql`;
- `event-trigger-inventory.txt`;
- `migration-ledger.txt` and `migration-ledger.sql` with version/name only;
- `recovery-files.sha256`, metadata, and tool-version files.

Workflow run `33060553416` generated the first v2 bundle from protected `main@33e5391937ed0a9b01d719259150d8cf7d61d568`. The artifact was independently inspected and its uploaded ZIP digest was `ffa6d91792776f5b43dbd6a6bd003e5243c875b77c7e8d4e8f4219795cdb4670`. The schema remained `100993` bytes with the same accepted SHA-256.

A truly new hosted Supabase restore then found an additional portability boundary: fresh-project **default ACL** inheritance grants application roles broader access to postgres-created public objects before the database-level event-trigger guards are restored. V2 therefore cannot be accepted as self-sufficient from-zero recovery proof.

The disposable hosted target began with `0` public tables, `0` public routines, `0` public event triggers, and no application migration table. After v2 schema/event-trigger restore it had RLS enabled on all `9 / 9` CRM tables, but inherited direct CRM table grants `63 / 63 / 63` and CRM function EXECUTE counts `26 / 26 / 31` for `anon / authenticated / service_role`. The primary fingerprint expanded to 389 lines. Production itself did not drift.

## Recovery Bundle v3

Recovery Bundle v3 adds `post-schema-security.sql` and the frozen authority `supabase/baseline/recovery_service_role_rpc_allowlist.txt`.

`post-schema-security.sql` is restricted to:

- default privileges for **role `postgres` in schema `public`**;
- already-restored **postgres-owned** public relations, sequences, and functions;
- exact re-grant of `service_role EXECUTE` to the accepted 12 CRM RPC signatures.

It must not alter `supabase_admin` defaults, must not grant direct CRM access to `anon` or `authenticated`, and must not mutate customer rows. The v3 workflow reads Production catalog metadata and fails closed unless the live RPC allowlist and current security-origin counts still match the accepted authority.

See `RECOVERY_BUNDLE_V3.md` for the detailed from-zero evidence and v3 acceptance boundary.

## Required restore order

Final v3 recovery on a **new, isolated, disposable Supabase project** must use exactly this order:

1. `schema.sql`
2. `event-triggers.sql`
3. `post-schema-security.sql`
4. `migration-ledger.sql`

Then run the read-only recovery checks and require:

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- supplemental guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public recovery fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- migration ledger: `51` entries with head `20260825075808 / post_p5_rate_limit_concurrency`.

The current hosted investigation demonstrated that the v3 reconciliation design can converge a genuinely fresh target to all three accepted fingerprints and the 51-entry migration head. The future-object default-privilege probe also passed and rolled back its synthetic table, sequence, and function.

Final closure still requires a **fresh v3 artifact from protected main** and a restore using the v3 files without ad-hoc repair.

## Credential and data safety

- Never commit the database password or complete credential-bearing connection string.
- Never paste database credentials into issue/PR descriptions, logs, screenshots, chat transcripts, or backups.
- A service-role/API secret is **not** a PostgreSQL database password and must never be substituted for one.
- The workflow may reference encrypted `SUPABASE_DB_URL`, but it must mask and never print it.
- Do not export customer rows or Vault plaintext.
- Do not commit generated `schema.sql` or recovery-bundle contents to this public repository.
- Never run the synthetic cloud recovery acceptance script against Production.

## Synthetic acceptance boundary

`supabase/baseline/p0_cloud_recovery_acceptance.sql` is restricted to a **new, isolated, disposable Supabase project**. Static review confirms it generates synthetic values, requires the recovery CRM target to be empty, starts an explicit transaction, performs recovery assertions, and ends in `ROLLBACK`.

The connected SQL execution safety layer blocked execution of the full credential/reveal payload during this recovery run, so that full synthetic script has **not** yet passed in the current hosted recovery exercise. Do not infer completion from the fingerprint matches alone.

## What does not count as completion

The following do not close the deliverable by themselves:

- fingerprints without a portable artifact;
- the first `schema.sql` without event-trigger and migration-ledger adjuncts;
- Recovery Bundle v2 without post-schema default-ACL reconciliation;
- repository migration files alone while the known 2026-08-13/14 migration-history gap remains;
- restoring into a project that already contains CRM schema;
- an ad-hoc security repair not represented in the final recovery bundle;
- successful fingerprints without the remaining synthetic recovery acceptance.

## Closure condition

Issue #93 remains open until a fresh Recovery Bundle v3 generated from protected `main` is independently checksum-inspected, restored into a truly empty disposable hosted target in the documented order, reproduces the accepted fingerprints/migration head without ad-hoc repair, and completes the remaining synthetic recovery acceptance restricted to that target.
