# Current Production Database Authority — 2026-08-30

This file is the current database-specific override for older checkpoint text in `CURRENT_STATE.md` and `CURRENT_RECOVERY_VERIFICATION.md`. Historical Recovery Bundle v3 / 2026-08-27 acceptance evidence remains valid for its original 51-migration checkpoint and must not be rewritten as if the old artifact contained later migrations.

## Current Production checkpoint

Project: `avahcwyxparbcjdfglzx`

Fresh read-only verification after the reviewed account-correspondence migration:

- migration rows: `52`
- migration head: `20260830071649 / client_account_safe_summary_correspondence`
- repository migration: `supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql`
- rollback: `supabase/rollback/20260830071649_client_account_safe_summary_correspondence.sql`
- primary fingerprint: `200 / 8ff7dd1447bf2cea9802438f91e8e1d3bf34bc7f7b4878592dd2eca8b06da7f9`
- three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`
- wider-public fingerprint: `225 / b89328f5548d4787a650b7f079bc1843125cc7c1b550d959a8cb4df2b2df04f2`
- CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`
- `crm_client_account_safe_summary(text,text)`: `SECURITY DEFINER`; `anon=false`; `authenticated=false`; `service_role=true`; Facebook/TikTok/Google/Instagram id-keyed safe-summary arrays present.

The migration changes a server-only safe-summary function shape. It does not write customer rows and does not broaden browser-role privileges.

## Historical predecessor retained

The immediately preceding accepted Production checkpoint remains historical evidence:

- `20260825075808 / post_p5_rate_limit_concurrency`
- migration rows: `51`
- primary `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`
- guard `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`
- wider-public `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`.

The accepted **future-object default-privilege hardening** boundary remains `20260825040850 / post_p5_public_default_privilege_guard`; this new function replacement does not weaken it.

## Recovery authority

Recovery Bundle v3 (workflow run `33079493119`) remains the accepted portable recovery **base through 51 migrations / `20260825075808`**. Its accepted artifact hashes, fresh-hosted restore proof, rollback-clean synthetic acceptance, and original 51-row migration ledger remain historical truth.

Until a newer bundle is generated and independently accepted, recovery to current Production is:

1. restore accepted Recovery Bundle v3 in its documented order;
2. apply `supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql`;
3. verify migration count/head `52 / 20260830071649`;
4. verify primary `200 / 8ff7dd1447...`, guard `9 / 2a6c96fe...`, wider-public `225 / b89328f5...`;
5. verify CRM EXECUTE remains `0 / 0 / 12`, RLS/default-deny/event-trigger invariants remain intact;
6. run the existing transaction-contained synthetic recovery acceptance only on a disposable target and prove rollback-clean state.

A mismatch is an investigation trigger, not authorization to broaden privileges or repair Production automatically.
