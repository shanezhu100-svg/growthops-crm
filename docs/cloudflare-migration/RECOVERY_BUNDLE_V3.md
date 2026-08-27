# Recovery Bundle v3 Authority

Last reviewed: 2026-08-27

This document records the from-zero hosted Supabase restore evidence that upgraded the GrowthOps CRM recovery bundle from v2 to v3. It is recovery-test authority only; it does not authorize Production mutation or automatic rollback.

## Why v3 exists

Recovery Bundle v2 fixed two omissions in the first real `schema.sql`: database-level event-trigger objects and the safe migration `version/name` ledger. A truly new hosted Supabase recovery project then exposed a third portability boundary.

A fresh Supabase project starts with platform default privileges that allow `anon`, `authenticated`, and `service_role` broader access to objects subsequently created by `postgres`. During restore, `schema.sql` creates the CRM tables/functions **before** the four database-level event triggers are restored. The DDL guards therefore cannot retroactively clean those already-created objects.

The first v2 from-zero attempt observed:

- empty start: `public_tables=0`, `public_routines=0`, `public_event_triggers=0`, and no application migration table;
- after schema/event-trigger restore, RLS was correctly enabled on `9 / 9` CRM tables;
- but direct CRM table grants were `63 / 63 / 63` for `anon / authenticated / service_role`;
- CRM function EXECUTE counts were `26 / 26 / 31` instead of the accepted `0 / 0 / 12`;
- the primary fingerprint expanded to `389` inventory lines instead of `200`.

This was a recovery-target default-ACL inheritance problem, not Production drift.

## v3 component

Recovery Bundle v3 adds:

`post-schema-security.sql`

The adjunct is intentionally narrow. It:

1. changes default privileges only for role `postgres` in schema `public`;
2. revokes application-role privileges only from already-restored **postgres-owned** public relations, sequences, and functions;
3. revokes function EXECUTE from `PUBLIC`, `anon`, `authenticated`, and `service_role` before rebuilding the allowlist;
4. restores `service_role EXECUTE` to exactly 12 accepted CRM RPC signatures;
5. never alters `supabase_admin` default privileges;
6. never grants direct relation/function access to `anon` or `authenticated`;
7. contains no customer-row mutation.

The exact 12-RPC recovery allowlist is pinned in:

`supabase/baseline/recovery_service_role_rpc_allowlist.txt`

The v3 workflow also queries the live authorized Production catalog and fails closed unless that live allowlist still matches the pinned file exactly.

## Required restore order

On a **new, isolated, disposable Supabase project**, restore in exactly this order:

1. `schema.sql`
2. `event-triggers.sql`
3. `post-schema-security.sql`
4. `migration-ledger.sql`

Do not reorder steps 2 and 3. The post-schema security reconciliation is designed for objects restored before the event-trigger guards existed, while the restored event triggers protect future DDL after the recovery checkpoint.

## Hosted from-zero evidence already obtained

Disposable recovery project used for the current investigation:

`bxobzbgcqkgnukccixng / growthops-recovery-bundle-v2-test / ap-southeast-1`

It was created only after the organization reported a current project cost of `$0/month`; Production was not modified. The older `growthops-p0-recovery-test` project was paused to free the Free Plan active-project slot and was not deleted.

After applying the exact post-schema security reconciliation and exact original function definitions from the bundle, the disposable hosted target matched all accepted Production comparison checkpoints:

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- supplemental guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public recovery fingerprint: `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`;
- safe migration ledger: `51` entries, head `20260825075808 / post_p5_rate_limit_concurrency`.

The future-object default-privilege probe also passed on the disposable target and proved its synthetic table, sequence, and function were all rolled back.

Supabase Security Advisor returned only the expected `RLS enabled / no policy` INFO notices for the RPC-only/default-deny CRM tables. Performance Advisor returned only unused-index INFO notices expected on a newly restored database with no business traffic. Those notices do not authorize schema changes.

## What is still required

Issue #93 remains open. The current evidence proves that **the v3 security reconciliation design** can converge a fresh hosted target to the accepted Production catalog/security state, but final closure still requires:

1. PR/Gate acceptance and merge of the v3 workflow/control files;
2. a fresh Recovery Bundle v3 artifact generated from protected `main`;
3. independent checksum/artifact inspection;
4. restoration using the v3 files in their exact documented order, without ad-hoc security repair;
5. re-running the three accepted fingerprints and 51-entry migration-head check;
6. running `supabase/baseline/p0_cloud_recovery_acceptance.sql` only on a disposable target and requiring its synthetic transaction to roll back.

The full synthetic cloud acceptance script has been statically reviewed: it uses generated synthetic values, requires the recovery CRM target to be empty, begins an explicit transaction, emits `P0_CLOUD_RECOVERY_ACCEPTANCE_OK` only after assertions, and ends with `ROLLBACK`. The connected SQL execution safety layer blocked execution of the full credential/reveal test payload, so **that script has not yet been executed successfully in this recovery run**. Do not claim otherwise.

## Safety boundaries

- Never run `p0_cloud_recovery_acceptance.sql` against Production.
- Never export customer rows or Vault plaintext into the recovery bundle.
- Never print or commit a database password, full credential-bearing PostgreSQL URL, Supabase server secret, or customer secret material.
- A service-role/API secret is not a PostgreSQL database password.
- Do not modify `supabase_admin` defaults to force a recovery fingerprint match.
- A fingerprint mismatch is an investigation trigger, not authorization to repair Production.
