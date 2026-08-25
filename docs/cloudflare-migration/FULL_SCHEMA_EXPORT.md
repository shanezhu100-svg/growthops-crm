# Full Schema Export Recovery Procedure

Last reviewed: 2026-08-24

This runbook defines the trusted path for closing the outstanding P0 **full schema-only export** recovery deliverable. It complements, but does not replace, the deterministic comparison checks in `CURRENT_RECOVERY_VERIFICATION.md`.

## Current status

The full schema-only export is **not yet complete**.

Current automation can query the Production database and recompute the accepted recovery fingerprints, but that is not equivalent to a portable schema dump. The connected Supabase automation surface does not currently expose a database-password retrieval action, temporary/JIT database-access action, or schema/backup export action. The current execution environment was also rechecked at this review and does not provide the Supabase CLI, `pg_dump`, `psql`, or Docker.

Do not mark this deliverable complete until a real export artifact has been produced through an authorized database connection and independently verified.

## Preferred export path

Use the current Supabase CLI database dump workflow with an authorized database connection string.

Supabase's CLI `db dump` path is preferred over assembling schema from catalog queries because it runs the PostgreSQL dump machinery with Supabase-specific filtering for managed/internal schemas and reserved roles.

For a schema-only recovery artifact, the normal CLI dump is the relevant form:

```sh
supabase db dump --db-url "$SUPABASE_DB_URL" -f schema.sql
```

Do not add `--data-only` or `--role-only` to the schema artifact. If roles or data are ever required for a broader recovery package, create them as separate reviewed artifacts rather than mixing customer data into this schema-only deliverable.

## Required prerequisites

Before running the dump, all of these must be true:

1. an authorized Production database connection string is available through the Supabase Connect/Database settings flow;
2. the database password is available to the authorized operator without committing or logging it;
3. Supabase CLI is installed in a trusted environment;
4. Docker is available for the CLI dump workflow, or another officially supported Supabase dump environment is used;
5. the target directory is outside the public repository and is access-controlled;
6. the operator has confirmed the connection points to the canonical Production project `avahcwyxparbcjdfglzx` before the command is run.

A service-role/API secret is **not** a PostgreSQL database password and must not be substituted into a Postgres connection string.

## Credential safety rules

- Never commit the database password or complete credential-bearing connection string to GitHub.
- Never paste the password into issue/PR descriptions, build logs, screenshots, chat transcripts, Pages/Vercel logs, or normal CRM backups.
- Prefer an ephemeral environment variable or an approved local secret store for the connection URL.
- Do not reset the Production database password merely to make an automated dump possible without an explicit credential-rotation decision and approval.
- Do not create a temporary privileged database role/password solely to bypass the normal backup path without a separately reviewed security change.
- Delete local credential-bearing shell history/files after the authorized export workflow according to the operator's secret-handling policy.

## Export procedure

1. Obtain the current Session Pooler or direct database connection string from the authorized Supabase project Connect flow.
2. Supply the database password only in the trusted export environment.
3. Confirm the target project ref is `avahcwyxparbcjdfglzx`.
4. Run the schema export to a non-repository path:

```sh
mkdir -p ./private-recovery-export
supabase db dump --db-url "$SUPABASE_DB_URL" -f ./private-recovery-export/schema.sql
```

5. Confirm the command exits successfully and the artifact is non-empty.
6. Compute a local checksum without printing database credentials:

```sh
sha256sum ./private-recovery-export/schema.sql
```

7. Inspect the artifact for obvious credential leakage before long-term storage. A schema-only artifact may legitimately contain object/function definitions and privilege statements, but it must not contain live customer password/2FA values or the Production database password.
8. Store the artifact in an approved access-controlled backup location. Do **not** commit the full dump to this public repository unless a separate security review has established that the exact artifact is safe for public source control.
9. Record only safe metadata in the repository recovery documentation: export date, tool/version, project ref, artifact checksum, storage authority/location label, and verification result. Do not record the credential-bearing connection string.

## Verification after export

A schema file existing on disk is not enough. Verify the artifact against current Production recovery truth:

1. Re-run `supabase/baseline/p0_schema_security_fingerprint.sql` on Production and confirm the accepted current primary checkpoint unless a reviewed migration intentionally changed it.
2. Re-run `supabase/baseline/post_p5_crm_guard_security_fingerprint.sql` and confirm the accepted guard checkpoint unless a reviewed guard migration intentionally changed it.
3. Record the migration-ledger head from `P0_MIGRATION_LEDGER.md` / current Production.
4. Prefer restoring the schema into an empty isolated recovery target and re-running `CURRENT_RECOVERY_VERIFICATION.md` before declaring the dump proven restorable.
5. Keep `supabase/baseline/p0_cloud_recovery_acceptance.sql` restricted to a disposable empty isolated recovery project; never run that synthetic-data acceptance script on Production.

Current comparison checkpoints at this review are:

- primary CRM fingerprint: `200 / bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1`;
- supplemental CRM guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- accepted Production migration head: `20260825040850 / post_p5_public_default_privilege_guard`.

## What does not count as completion

None of the following closes the full-schema deliverable by itself:

- `p0_schema_security_fingerprint.sql` output;
- the supplemental guard fingerprint;
- `p0_recovery_inventory.sql` output;
- a list of tables, columns, functions, or extensions returned by the management connector;
- generated TypeScript database types;
- repository migration files alone while the known 2026-08-13/14 migration-history gap remains;
- copying SQL definitions manually from catalog queries;
- a Production dashboard screenshot;
- a data backup whose schema contents have not been independently verified.

These are useful evidence, but they do not replace a trusted portable dump.

## Current blocker and safe next action

The current blocker is operational authorization/tooling, not a known Production database defect:

- no database password/credential-bearing connection string is available through the connected automation tools;
- no temporary/JIT database-access or schema-export/download action is exposed by the connected Supabase tool surface;
- the current execution environment has no Supabase CLI / Docker / `pg_dump` / `psql` toolchain;
- the public repository contains no database dump credential.

Therefore the safe next action is to perform the official dump in a trusted operator environment once an authorized database connection and toolchain are available. Until then, keep this item explicitly **open** and continue using the current read-only fingerprints/inventory for comparison—not as a substitute for the dump.
