# P0 Supabase Migration Ledger — 2026-08-25 Appendix

Checkpoint date: 2026-08-25

This appendix extends the historical `P0_MIGRATION_LEDGER.md` without rewriting its 2026-08-21 checkpoint or obscuring the known 2026-08-13/14 remote-history-only gap.

## Newly verified forward migration

Production `supabase_migrations.schema_migrations` was re-read after the Post-P5 concurrency deployment and the following later forward migration was verified:

| Remote version | Migration name | Repository file | Status |
| --- | --- | --- | --- |
| `20260825075808` | `post_p5_rate_limit_concurrency` | `supabase/migrations/20260825_post_p5_rate_limit_concurrency.sql` | **Production applied; repository-backed** |

Associated retained recovery/verification artifacts:

- exact rollback: `supabase/rollback/20260825_post_p5_rate_limit_concurrency.sql`;
- preflight: `supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql`;
- read-only post-check: `supabase/baseline/post_p5_rate_limit_concurrency_check.sql`;
- canonical regression test: `test_post_p5_rate_limit_concurrency.py`;
- acceptance record: `docs/cloudflare-migration/POST_P5_RATE_LIMIT_CONCURRENCY.md`.

## Ledger-gap statement

This new migration is **not** a new remote-history-only gap. Its genuine forward SQL, rollback, preflight, post-check, and regression source are retained in GitHub.

The unresolved historical gap therefore remains the same eleven 2026-08-13/14 entries already identified in `P0_MIGRATION_LEDGER.md`. Do not reconstruct guessed historical SQL for those entries.

## Current comparison anchor after this migration

Because the migration intentionally changes three `crm_*` function definitions, the deterministic primary CRM catalog/security fingerprint was refreshed after application:

- inventory lines: `200`;
- SHA-256: `77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`.

The supplemental three-guard fingerprint remains unchanged:

- guard inventory lines: `9`;
- guard SHA-256: `2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`.

These fingerprints are comparison anchors only and do not replace the outstanding full schema-only `pg_dump`/equivalent recovery deliverable.
