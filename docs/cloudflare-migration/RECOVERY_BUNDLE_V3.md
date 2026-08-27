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

The final `post-schema-security.sql` merged to protected main was re-applied to that disposable target as an idempotence check. After re-application, all three accepted fingerprints remained unchanged and the temporary validation migration entry was removed so the recovery ledger returned to exactly 51 entries with the accepted head.

## Accepted Recovery Bundle v3 artifact

Recovery Schema Bundle v3 workflow run `33079493119` completed successfully from protected:

`main@89e1904a521c41ab1b35eb29ef25c2834bf76538`

Accepted artifact evidence:

- artifact: `growthops-schema-recovery-bundle-v3-33079493119`;
- artifact ID: `9649406110`;
- artifact ZIP SHA-256: `c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7`;
- artifact size: `22424` bytes;
- artifact file count: `12`;
- `schema.sql`: `100993` bytes;
- `schema.sql` SHA-256: `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`;
- `event-triggers.sql`: exactly four `CREATE EVENT TRIGGER` statements;
- `migration-ledger.txt`: exactly 51 entries with head `20260825075808|post_p5_rate_limit_concurrency`;
- `post-schema-security.sql`: exactly 12 explicit CRM `service_role EXECUTE` grants;
- `post-schema-security.sql` SHA-256: `d811cfa142e2268b4ef4746f7bc87f837cc21b590b3716a3f834b68b36abbfe0`;
- zero `supabase_admin` default-ACL alterations in `post-schema-security.sql`;
- zero `anon` / `authenticated` grants in `post-schema-security.sql`;
- every file listed in `recovery-files.sha256` independently verified `OK`;
- metadata records `contains_customer_rows=false`, `contains_migration_statement_arrays=false`, `touches_supabase_admin_defaults=false`, and `empty_target_restore_required=true`.

The workflow logs kept `SUPABASE_DB_URL` masked as `***`; no database password, complete PostgreSQL URL, or Supabase server secret was observed in the run logs.

This accepts the **integrity and scope of the v3 artifact**. It does not by itself close #93.

## What is still required

Issue #93 remains open. PR/Gate acceptance, v3 workflow merge, fresh artifact generation, and independent artifact/checksum inspection are now complete.

Final closure still requires:

1. a **second truly fresh hosted disposable Supabase project** restored directly from the accepted v3 artifact in the exact documented order, with no ad-hoc ACL or function-definition repair;
2. exact matches for the primary, guard, and wider-public fingerprints plus the 51-entry migration-head check on that fresh v3 restore;
3. `supabase/baseline/p0_cloud_recovery_acceptance.sql` executed only on a disposable target and its synthetic transaction proven rolled back.

The full synthetic cloud acceptance script has been statically reviewed: it uses generated synthetic values, requires the recovery CRM target to be empty, begins an explicit transaction, emits `P0_CLOUD_RECOVERY_ACCEPTANCE_OK` only after assertions, and ends with `ROLLBACK`. The connected SQL execution safety layer blocked execution of the credential/reveal payload, so **that script has not yet been executed successfully in this recovery run**. Do not claim otherwise.

## Safety boundaries

- Never run `p0_cloud_recovery_acceptance.sql` against Production.
- Never export customer rows or Vault plaintext into the recovery bundle.
- Never print or commit a database password, full credential-bearing PostgreSQL URL, Supabase server secret, or customer secret material.
- A service-role/API secret is not a PostgreSQL database password.
- Do not modify `supabase_admin` defaults to force a recovery fingerprint match.
- A fingerprint mismatch is an investigation trigger, not authorization to repair Production.
