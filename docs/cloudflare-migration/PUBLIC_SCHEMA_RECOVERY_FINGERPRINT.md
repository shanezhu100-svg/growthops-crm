# Supplemental Public Schema Recovery Fingerprint

Checkpoint date: 2026-08-25
Supabase project: `avahcwyxparbcjdfglzx`

This document records a deterministic, read-only recovery comparison fingerprint for the wider PostgreSQL `public` schema. It complements the historical `crm_*` primary fingerprint and the three-guard Post-P5 fingerprint.

It is **not** a schema dump, does not make the repository fully restorable from zero, and does not close the outstanding `FULL_SCHEMA_EXPORT.md` deliverable.

## Why this supplemental fingerprint exists

The primary `supabase/baseline/p0_schema_security_fingerprint.sql` deliberately preserves its historical `crm_*` comparison contract. The three-guard fingerprint then adds the repository-managed GrowthOps DDL guards. Those two checks are strong security anchors but do not, by themselves, fingerprint every recovery-relevant object or ACL characteristic in `public`.

`supabase/baseline/p0_public_schema_recovery_fingerprint.sql` broadens comparison coverage while remaining read-only and data-free.

## Coverage

The fingerprint hashes deterministic catalog lines for:

- the `public` schema owner and ACL;
- `public` tables, partitioned tables, sequences, views, materialized views and foreign tables, including owner/ACL/RLS flags;
- all `public` columns, including type, nullability, default, identity and generated-column metadata;
- constraints and their definitions;
- indexes and definitions;
- non-internal table triggers and definitions;
- all `public` functions/procedures, including identity arguments, owner, security-definer/leakproof/volatility/parallel/config/ACL metadata and `pg_get_functiondef()`;
- effective EXECUTE truth for `anon`, `authenticated`, and `service_role` across every `public` routine;
- `public` RLS policies;
- event triggers whose handler function lives in `public`;
- global or `public` default ACL rows;
- installed extension name/version/schema/relocatable metadata.

The query emits only:

- an inventory-line count; and
- a SHA-256 digest.

It does **not** emit the underlying function definitions, customer table rows, Vault plaintext, credential values, or other application data.

## Accepted Production checkpoint

The query was executed twice consecutively against Production on 2026-08-25 with identical results:

- `inventory_lines = 225`
- `public_recovery_sha256 = a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`

A separate read-only count inventory at the same checkpoint observed:

- public tables: `9`;
- public sequences: `1`;
- public views: `0`;
- public materialized views: `0`;
- public indexes: `27`;
- public constraints: `30`;
- non-internal public table triggers: `5`;
- public routines: `44` (`40` `crm_*` plus `4` non-CRM routines);
- public RLS policies: `0`;
- event triggers whose handler function is in `public`: `4`.

The four non-CRM public routines were exactly:

- `growthops_crm_acl_guard_ddl()`;
- `growthops_crm_rls_guard_ddl()`;
- `growthops_public_noncrm_function_acl_guard_ddl()`;
- `rls_auto_enable()`.

The four public-function event triggers were exactly:

- `ensure_rls`;
- `growthops_crm_acl_guard_ddl`;
- `growthops_crm_rls_guard_ddl`;
- `growthops_public_noncrm_function_acl_guard_ddl`.

Installed extension metadata included `pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, and `uuid-ossp` at their then-current versions. Extension version changes can legitimately change this supplemental hash and therefore require evidence-based review rather than automatic rollback.

## Relationship to the other recovery anchors

At this checkpoint the three current comparison anchors are:

1. primary CRM schema/security fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
2. supplemental three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
3. supplemental wider-public recovery fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`.

The accepted Production migration head remains:

`20260825075808 / post_p5_rate_limit_concurrency`

These fingerprints answer different comparison questions. They are not interchangeable and none is a portable schema export.

## Drift handling

If this supplemental hash changes unexpectedly:

1. do not run a rollback solely because the hash changed;
2. recompute the primary and three-guard fingerprints;
3. inspect the exact reviewed schema/ACL/function/extension change that explains the wider-public difference;
4. determine whether the change is a GrowthOps migration, a reviewed platform/extension change, or an unauthorized drift;
5. refresh this checkpoint only after that cause is understood and accepted;
6. use a migration-specific rollback only when a specific GrowthOps database change is proven to be the fault.

A platform-managed extension upgrade can change this hash without changing the CRM security contract, which is why the narrower primary and three-guard fingerprints remain independently authoritative.

## Recovery limitation

This fingerprint intentionally does **not** attempt to reconstruct SQL from `pg_catalog`, recover the known 2026-08-13/14 historical migration SQL gap, or replace `supabase db dump` / `pg_dump`.

The full schema-only export remains open until an authorized portable dump artifact is produced and independently verified according to `FULL_SCHEMA_EXPORT.md`.
