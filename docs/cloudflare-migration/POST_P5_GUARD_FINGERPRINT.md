# Post-P5 GrowthOps Guard Recovery Fingerprint

Checkpoint date: 2026-08-24

## Why this supplemental fingerprint exists

The long-lived CRM catalog/security fingerprint in `supabase/baseline/p0_schema_security_fingerprint.sql` intentionally preserves its historical `crm_*` comparison contract. It covers CRM columns, constraints, indexes, table triggers, `crm_*` functions, application-role function EXECUTE truth, direct application-role table grants, RLS flags, and policies.

Three later Post-P5 controls sit outside that namespace contract:

- `public.growthops_crm_acl_guard_ddl()` and its `growthops_crm_acl_guard_ddl` event trigger;
- `public.growthops_crm_rls_guard_ddl()` and its `growthops_crm_rls_guard_ddl` event trigger;
- `public.growthops_public_noncrm_function_acl_guard_ddl()` and its `growthops_public_noncrm_function_acl_guard_ddl` event trigger.

The first two protect the accepted CRM ACL/RLS boundary. The third closes future non-`crm_*` function/procedure EXECUTE exposure in `public` without altering Supabase platform schemas. Changing or dropping any of these guards does not necessarily change the primary `crm_*` fingerprint. This supplemental read-only fingerprint closes that recovery-comparison gap without rewriting historical P0 hashes.

## What is fingerprinted

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql` deterministically records:

- the complete function definitions for the three repository-managed guard functions;
- their owners;
- effective `EXECUTE` truth for `anon`, `authenticated`, and `service_role`;
- all three event-trigger names;
- event type;
- enabled state;
- configured event tags;
- each event-trigger-to-function binding.

It does not take ownership of unrelated Supabase/platform event triggers or reconstruct missing historical 2026-08-13/14 SQL.

## Current Production checkpoint

A fresh read-only execution against the canonical Production Supabase project on 2026-08-24 after `20260825040850 / post_p5_public_default_privilege_guard` returned:

- `guard_inventory_lines = 9`;
- `guard_security_sha256 = 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`.

The same inspection confirmed all three GrowthOps event triggers are `ddl_command_end`, enabled, and bound to their expected `postgres`-owned `SECURITY DEFINER` functions with fixed `pg_catalog` search paths. The guard functions are not executable by `anon`, `authenticated`, or `service_role`.

The new public non-CRM guard is intentionally limited to `CREATE/ALTER FUNCTION` and `CREATE/ALTER PROCEDURE` in `public`; the existing CRM ACL guard remains authoritative for the exact `crm_*` service-role function allowlist.

## Recovery use

Re-run the supplemental SQL together with `p0_schema_security_fingerprint.sql`:

1. after any migration that changes a repository-managed GrowthOps DDL guard;
2. before and after a database rollback that touches ACL/RLS/default-privilege guard behavior;
3. when validating a restored database against current Production security controls;
4. whenever the primary CRM catalog/security checkpoint is refreshed after schema/ACL/function changes.

A mismatch is a comparison signal, not permission to recreate or broaden privileges automatically. Inspect the exact guard migration/rollback package and current Production state before taking database action.

## Boundary

This fingerprint is not a full schema backup and does not close the outstanding full schema-only `pg_dump`/equivalent recovery deliverable. It only makes the three repository-managed Post-P5 DDL guard controls independently detectable during recovery comparison.
