# P5 Group 4 — Credential Safe Summary Privilege Hardening

Last updated: 2026-08-23

## Status

Groups 1–3 predecessor gates are complete. Group 4 live database preflight is PASS. **Execution package is prepared but not applied to Production.** Cloudflare exact-head verification remains required before Production apply.

This branch is reconstructed directly onto accepted `main@b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89`.

## Exact scope

Group 4 contains exactly one live credential safe-summary RPC:

- `crm_client_account_safe_summary(text,text)`

This is a real final-runtime dependency. The credential UI uses it to render login identifiers plus credential-presence booleans without returning password or 2FA plaintext.

## Accepted predecessor baseline

Current accepted Production baseline after Group 3:

- `main`: `b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89`;
- CRM functions: `40`;
- anon EXECUTE: `6`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`;
- canonical security fingerprint: `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

## BFF/runtime security boundary

Both Vercel and Cloudflare `/api/crm` BFFs:

- classify the RPC under `AUTH_RPCS`, never `PUBLIC_RPCS` or `LOGIN_RPCS`;
- require the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict session cookie;
- reject missing cookie with `401 SESSION_REQUIRED` before any upstream call;
- overwrite browser-supplied `p_token` with the server-read cookie token;
- require `GROWTHOPS_SUPABASE_SECRET_KEY` with `sb_secret_` identity and have no publishable-key fallback;
- enforce same-origin before dispatch.

The final shipped credential runtime still depends on `crm_client_account_safe_summary` and keeps retired `crm_client_credential_status` out of runtime.

## Live Production function preflight

Read-only Production inspection confirms the exact function is currently:

- `SECURITY DEFINER`;
- `anon=true`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`.

Its live definition still:

- calls `crm_session_context`;
- remains workspace-scoped;
- permits only ADMIN/OPS;
- reads the workspace secret tree only to derive credential-presence flags;
- does not call any `crm_reveal*` RPC;
- returns identifiers plus `hasPassword` / `has2FA` booleans;
- does not expose `password`, `2fa`, `loginPassword`, `login_password`, or generic `value` output keys.

No Vault plaintext was read or returned during this audit.

## Preparation exact-head evidence

Preparation head: `84733db0d1659d97ca31ee781923658f57131fe4`.

Vercel:

- deployment `dpl_2EsAns1RU9TLZVNrWrEnffWgijrY`;
- state `READY`;
- `P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK` PASS;
- `P5_GROUP4_SAFE_SUMMARY_BFF_OK` PASS;
- Group 1–3 gates and P3/P4 attack regression remain PASS.

Cloudflare:

- the browser connector became unavailable before the rebuilt Group 4 exact-head deployment could be independently inspected;
- therefore Cloudflare exact-head verification remains a hard pre-apply gate;
- Production must not be changed while this evidence is missing.

## Prepared execution package

Forward migration:

`supabase/migrations/20260823_p5_group4_revoke_safe_summary_anon_exec.sql`

It contains exactly one statement:

```sql
revoke execute on function public.crm_client_account_safe_summary(text, text) from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group4_restore_safe_summary_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group4_safe_summary_anon_exec_check.sql`

Dedicated static gate:

`test_p5_group4_safe_summary_revocation.py`

Expected privilege transition after a later Production apply:

- anon CRM EXECUTE: `6 -> 5`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

## Execution gate

Before applying Production, the execution-package exact head must independently pass Vercel and Cloudflare builds, including:

- all predecessor Group 1–3 gates;
- P3/P4 attack regression;
- `P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK`;
- `P5_GROUP4_SAFE_SUMMARY_BFF_OK`;
- `P5_GROUP4_SAFE_SUMMARY_REVOCATION_OK`;
- Cloudflare P1 output parity.

Immediately before apply, Production must still match:

- target `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false`;
- global `40 / 6 / 0 / 40`;
- RLS `9/9`;
- migration `20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`;
- fingerprint `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

## Automated gates

`test_p5_group4_safe_summary_candidate.py` enforces the authenticated-only BFF route, final-runtime dependency, narrow output contract, database definition guards, accepted Group 3 baseline, and exact execution-package presence.

`test_p5_group4_safe_summary_bff.mjs` executes the path against both handlers and proves no-session rejection with zero upstream calls plus authoritative cookie-token substitution.

`test_p5_group4_safe_summary_revocation.py` enforces the one-RPC forward migration, exact inverse rollback, read-only post-check, and preserved BFF/session boundary.

Expected markers:

`P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK: safe-summary=auth-only-bff+final-runtime; output=identifier+presence-booleans-only; reveal-call=none; group3=accepted; production-change=none`

`P5_GROUP4_SAFE_SUMMARY_BFF_OK: no-session=401+zero-upstream; cookie-token=authoritative; both-platforms=pass`

`P5_GROUP4_SAFE_SUMMARY_REVOCATION_OK: revoke=1-safe-summary-anon-only; rollback=1-exact-grant; post-check=read-only; auth-bff=session-gated; expected-anon=5; service-role=40`

## Non-goals

Group 4 does not change credential values, reveal/unlock behavior, login/state/user-management behavior, Vault contents, database function bodies, tables, RLS, policies, session duration, CSP, DNS, WAF, CRM UI/business behavior, or Groups 5–6 privileges.
