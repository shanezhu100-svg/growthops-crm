# Post-P5 CRM Guard Recovery Fingerprint

Checkpoint date: 2026-08-24

## Why this supplemental fingerprint exists

The long-lived CRM catalog/security fingerprint in `supabase/baseline/p0_schema_security_fingerprint.sql` intentionally preserves its historical `crm_*` comparison contract. It covers CRM columns, constraints, indexes, table triggers, `crm_*` functions, application-role function EXECUTE truth, direct application-role table grants, RLS flags, and policies.

Two later Post-P5 controls sit outside that namespace contract:

- `public.growthops_crm_acl_guard_ddl()` and its `growthops_crm_acl_guard_ddl` event trigger;
- `public.growthops_crm_rls_guard_ddl()` and its `growthops_crm_rls_guard_ddl` event trigger.

Those guards protect the accepted CRM ACL/RLS boundary, but changing or dropping them does not necessarily change the primary `crm_*` fingerprint. This supplemental read-only fingerprint closes that recovery-comparison gap without rewriting historical P0 hashes.

## What is fingerprinted

`supabase/baseline/post_p5_crm_guard_security_fingerprint.sql` deterministically records:

- the complete function definitions for the two repository-managed guard functions;
- their owners;
- effective `EXECUTE` truth for `anon`, `authenticated`, and `service_role`;
- both event-trigger names;
- event type;
- enabled state;
- configured event tags;
- the event-trigger-to-function binding.

It does not take ownership of unrelated Supabase/platform event triggers or reconstruct missing historical 2026-08-13/14 SQL.

## Current Production checkpoint

A read-only execution against the canonical Production Supabase project on 2026-08-24 returned:

- `guard_inventory_lines = 6`;
- `guard_security_sha256 = d3491022f0827324c810d401123d6027c0c3d46498868a2b5520bbea54bae52f`.

The same inspection confirmed both GrowthOps event triggers are `ddl_command_end`, enabled, bound to their expected `postgres`-owned `SECURITY DEFINER` functions, and not executable by `anon` or `authenticated`.

## Recovery use

Re-run the supplemental SQL together with `p0_schema_security_fingerprint.sql`:

1. after any migration that changes either GrowthOps CRM DDL guard;
2. before and after a database rollback that touches ACL/RLS guard behavior;
3. when validating a restored database against current Production security controls;
4. whenever the primary CRM catalog/security checkpoint is refreshed after schema/ACL/function changes.

A mismatch is a comparison signal, not permission to recreate or broaden privileges automatically. Inspect the exact guard migration/rollback package and current Production state before taking database action.

## Boundary

This fingerprint is not a full schema backup and does not close the outstanding full schema-only `pg_dump`/equivalent recovery deliverable. It only makes the two repository-managed Post-P5 DDL guard controls independently detectable during recovery comparison.
