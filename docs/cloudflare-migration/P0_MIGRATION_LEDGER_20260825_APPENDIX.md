# P0 Supabase Migration Ledger — 2026-08-25 Appendix

Checkpoint date: 2026-08-25
Consolidated into `P0_MIGRATION_LEDGER.md`: 2026-08-25

This appendix is retained as the point-in-time acceptance note that first recorded the Post-P5 concurrency migration. Its current-head information has now been consolidated into `P0_MIGRATION_LEDGER.md`; use the main ledger as the current migration-history authority while preserving this appendix as historical evidence.

## Newly verified forward migration at this checkpoint

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

This migration is **not** a remote-history-only gap. Its genuine forward SQL, rollback, preflight, post-check, and regression source are retained in GitHub.

The unresolved historical gap therefore remains the same eleven 2026-08-13/14 entries identified in `P0_MIGRATION_LEDGER.md`. Do not reconstruct guessed historical SQL for those entries.

## Comparison anchor captured at this checkpoint

Because the migration intentionally changed three `crm_*` function definitions, the deterministic primary CRM catalog/security fingerprint was refreshed after application:

- inventory lines: `200`;
- SHA-256: `77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`.

The supplemental three-guard fingerprint remained:

- guard inventory lines: `9`;
- guard SHA-256: `2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`.

A later read-only recovery-audit step added the wider-public supplemental fingerprint `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`; that later evidence belongs to `PUBLIC_SCHEMA_RECOVERY_FINGERPRINT.md` and the consolidated main ledger, not to the original point-in-time claim of this appendix.

All fingerprints are comparison anchors only and do not replace the outstanding full schema-only `pg_dump`/equivalent recovery deliverable.
