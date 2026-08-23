# P5 Group 4 Candidate — Credential Safe Summary

Last updated: 2026-08-23

## Status

Preparation only. Groups 1–3 predecessor gates are complete. This Group 4 branch is reconstructed directly onto accepted `main@b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89` and does **not** change Production database privileges at this checkpoint.

## Candidate scope

Exactly one live RPC:

- `crm_client_account_safe_summary(text,text)`

This is a real final-runtime dependency. The credential UI uses it to render login identifiers plus credential-presence booleans without returning password or 2FA plaintext.

No Group 4 forward `REVOKE` migration is included yet. No Group 4 rollback migration is included yet. No Group 4 SQL has been applied to Production.

## Accepted predecessor baseline

Group 3 is complete and merged. Current accepted Production baseline:

- `main`: `b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89`;
- CRM functions: `40`;
- anon EXECUTE: `6`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`;
- canonical security fingerprint: `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

## Required security shape

Before any Group 4 privilege change, all of the following must remain true:

- both Vercel and Cloudflare `/api/crm` BFFs classify the RPC under `AUTH_RPCS`, never `PUBLIC_RPCS` or `LOGIN_RPCS`;
- the BFF requires the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict session cookie;
- missing cookie returns `401 SESSION_REQUIRED` before any upstream RPC call;
- any browser-supplied `p_token` is overwritten with the server-read cookie token;
- both BFFs require `GROWTHOPS_SUPABASE_SECRET_KEY` with `sb_secret_` identity and no publishable-key fallback;
- same-origin checks remain active before dispatch;
- final shipped credential runtime still depends on `crm_client_account_safe_summary` and keeps retired `crm_client_credential_status` out of runtime;
- the database function remains `SECURITY DEFINER`, calls `crm_session_context(p_token)`, is workspace-bound, and permits only ADMIN/OPS;
- the return object remains limited to identifiers plus `hasPassword` / `has2FA` booleans;
- the function does not call a reveal RPC and does not return password, 2FA, or generic secret plaintext;
- service_role EXECUTE remains present and authenticated EXECUTE remains absent.

The function may inspect Vault-backed credential fields only to derive boolean presence flags. That internal read must never broaden the returned JSON surface.

## Group 4 preflight gate

Before creating a revoke migration, require exact-current-state evidence that:

1. both exact-head Vercel and Cloudflare builds are green;
2. the executable BFF harness proves no-session `401 + zero upstream` and cookie-token authority on both platforms;
3. final runtime still uses the safe-summary path and excludes legacy credential-status;
4. live Production implementation retains the session/workspace/ADMIN-or-OPS/Vault-presence-only contract and no reveal call;
5. Production still shows `anon=true`, `authenticated=false`, `service_role=true` for this function;
6. accepted global baseline remains `40 / 6 / 0 / 40`, RLS `9/9`, migration `20260823064535`, and fingerprint `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

## Intended later privilege change

Only after the preflight passes may a dedicated Group 4 migration revoke `anon` EXECUTE from exactly:

`public.crm_client_account_safe_summary(text,text)`

Expected transition if no unrelated privilege change occurs:

- anon CRM EXECUTE: `6 -> 5`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

The later migration must ship with an exact inverse rollback and a read-only post-change privilege check. Any authenticated ADMIN/OPS safe-summary regression on either exact-head Preview is a rollback trigger.

## Preparation-stage automated gates

`test_p5_group4_safe_summary_candidate.py` enforces the authenticated-only BFF route, final-runtime dependency, narrow output contract, database definition guards, predecessor baseline, and preparation-only no-SQL rule.

`test_p5_group4_safe_summary_bff.mjs` executes the path against both handlers and proves no-session rejection with zero upstream calls plus authoritative cookie-token substitution.

Expected markers:

`P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK: safe-summary=auth-only-bff+final-runtime; output=identifier+presence-booleans-only; reveal-call=none; group3=accepted; production-change=none`

`P5_GROUP4_SAFE_SUMMARY_BFF_OK: no-session=401+zero-upstream; cookie-token=authoritative; both-platforms=pass`

## Non-goals

This preparation branch does not change credential values, reveal/unlock behavior, login/state/user-management behavior, Vault contents, database function bodies, grants, tables, RLS, policies, session duration, CSP, DNS, WAF, CRM UI/business behavior, or Groups 5–6 Production privileges.
