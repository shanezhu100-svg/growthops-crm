# Public Schema Recovery Fingerprint Acceptance

Accepted evidence date: 2026-08-25

This checkpoint records the acceptance evidence for the supplemental wider-`public` recovery fingerprint introduced by `supabase/baseline/p0_public_schema_recovery_fingerprint.sql`.

## Production evidence

The read-only fingerprint query was executed twice consecutively against Supabase Production project `avahcwyxparbcjdfglzx` and returned the same result both times:

- inventory lines: `225`;
- SHA-256: `a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`.

A companion read-only count inventory observed:

- 9 public tables;
- 1 public sequence;
- 27 public indexes;
- 30 public constraints;
- 5 non-internal public table triggers;
- 44 public routines, consisting of 40 `crm_*` routines plus `growthops_crm_acl_guard_ddl()`, `growthops_crm_rls_guard_ddl()`, `growthops_public_noncrm_function_acl_guard_ddl()`, and `rls_auto_enable()`;
- zero public RLS policies;
- four event triggers whose handler functions live in `public`.

The query emits only its inventory-line count and digest. It does not emit customer rows, Vault plaintext, credential values, or the underlying routine definitions.

## Relationship to accepted recovery truth

The wider fingerprint supplements, and does not replace, these accepted Production comparison anchors:

- primary CRM fingerprint: `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- migration head: `20260825075808 / post_p5_rate_limit_concurrency`.

The wider fingerprint intentionally also covers installed extension metadata. A reviewed platform-managed extension version change can therefore change `225 / a0078c5d...` without necessarily changing the narrower CRM security boundary. A mismatch is an investigation trigger, not authorization for an automatic rollback.

## Recovery limitation

This checkpoint does not close the P0 full schema-only export deliverable. It is catalog comparison evidence only and is not a portable `pg_dump` / `supabase db dump` artifact. The known 2026-08-13/14 migration-history gap remains unresolved, and repository fingerprints must not be presented as full disaster-recovery schema portability.
