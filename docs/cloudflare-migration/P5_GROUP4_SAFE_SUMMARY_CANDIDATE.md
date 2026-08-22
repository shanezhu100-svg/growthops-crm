# P5 Group 4 Candidate — Credential Safe Summary

Last updated: 2026-08-22

## Status

Preparation only. This stacked branch does **not** change Production database privileges. It is intentionally based on P5 Group 3 and must not advance ahead of Groups 1–3.

## Candidate scope

Exactly one live RPC:

- `crm_client_account_safe_summary(text,text)`

This is not dead code. The final credential UI intentionally uses this RPC to render login identifiers plus credential-presence booleans without returning credential plaintext.

No Group 4 forward `REVOKE` migration is included yet. No Group 4 rollback migration is included yet. No SQL is applied to Production by this preparation branch.

## Required security shape

The safe-summary path must retain all of these properties before any later privilege change:

- both Vercel and Cloudflare BFFs classify the RPC as authenticated only, never public/login;
- the BFF requires the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict session cookie;
- any browser-supplied `p_token` is overwritten by the server-read cookie token;
- the BFF requires server-side `GROWTHOPS_SUPABASE_SECRET_KEY` / `sb_secret_` identity with no publishable-key fallback;
- same-origin checks remain active before dispatch;
- final credential runtime still uses `crm_client_account_safe_summary` and keeps legacy `crm_client_credential_status` out of the shipped runtime;
- the database function still resolves `crm_session_context(p_token)` and permits only ADMIN/OPS;
- the database return object remains a safe summary: client/account identifiers plus `hasPassword` / `has2FA` booleans; it must not call a reveal RPC or return password / 2FA plaintext;
- service_role EXECUTE remains present and authenticated EXECUTE remains absent.

The function may inspect Vault-backed credential fields solely to derive presence booleans. That internal read is not permission to broaden the returned JSON surface.

## Required predecessor gates

Do not create or apply a Group 4 revoke migration until, in order:

1. P5 Group 1 / PR #21 completes real authenticated Cloudflare + Vercel acceptance, ADMIN unlock/reveal acceptance, merge, and post-merge Production verification;
2. P5 Group 2 / PR #22 completes its one-RPC retirement, rollback verification, merge, and Production fingerprint verification;
3. P5 Group 3 / PR #23 completes its three-RPC ADMIN user-management retirement, rollback verification, merge, and Production fingerprint verification;
4. Group 4 re-runs exact-current-state BFF, final-runtime, and live database preflight checks.

## Intended later privilege change

Only after every predecessor and preflight gate passes, a dedicated later migration may revoke `anon` EXECUTE from exactly `crm_client_account_safe_summary(text,text)` while preserving `service_role` EXECUTE.

If Groups 2 and 3 have already completed with no unrelated privilege changes, the expected anon-executable CRM RPC count immediately before Group 4 would be 6 and after Group 4 would be 5.

The later change must ship with an exact inverse rollback and a read-only post-change privilege check. Any failure to load the credential safe summary for an authenticated ADMIN/OPS session on either exact-head Preview is a rollback trigger.

## Non-goals

This preparation branch does not change credential values, reveal behavior, unlock behavior, login/state/user-management behavior, Vault contents, Session duration, database functions, grants, tables, RLS, policies, CSP, DNS, WAF, UI business logic, predecessor branch heads, or `main`.
