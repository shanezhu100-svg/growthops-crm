# P5 Group 3 Candidate — Admin User-Management RPCs

Last updated: 2026-08-22

## Status

Preparation only. This stacked branch does **not** change Production database privileges. It is intentionally based on P5 Group 2 and must not be advanced ahead of either Group 1 human acceptance or Group 2 acceptance.

## Candidate scope

The cohesive candidate set is exactly:

- `crm_list_users(text)`
- `crm_upsert_user(text, uuid, text, text, text, text, boolean)`
- `crm_delete_user(text, uuid)`

No forward `REVOKE` migration is included yet. No rollback migration is included yet. No SQL is applied to Production by this preparation branch.

## Why these RPCs form one later group

All three are live ADMIN user-management operations and are intentionally still reachable through the CRM server BFF. They therefore must not be treated as dead-code retirement like Group 2.

The security boundary is instead server-mediated:

- both Vercel and Cloudflare `/api/crm` BFFs classify all three under authenticated RPCs, never public/login RPCs;
- the browser session token is held in the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- for authenticated RPCs the BFF overwrites any browser-supplied `p_token` with the cookie session token;
- both BFFs require the server-side `GROWTHOPS_SUPABASE_SECRET_KEY` identity and reject publishable-key fallback;
- same-origin checks run before RPC dispatch;
- BFF safe logging records only bounded metadata and does not log request args, passwords, session tokens, or secret keys;
- the P3/P4 live database regression requires the user-management functions to use `crm_session_context`, workspace scoping, and ADMIN guards.

The live database implementation additionally protects self-disable/self-delete and last-admin cases, hashes changed passwords server-side, invalidates sessions after password changes, and writes server audit records. Those live checks must be re-verified immediately before any later privilege change.

## Required predecessor gates

Do not create or apply a Group 3 revoke migration until all of the following have completed in order:

1. P5 Group 1 real authenticated Cloudflare + Vercel Preview acceptance, ADMIN unlock/reveal acceptance, expected-head merge, and post-merge Production verification;
2. P5 Group 2 preflight, dedicated one-RPC migration/rollback/check, exact-head Preview verification, acceptance, merge, and post-merge Production fingerprint verification;
3. Group 3 exact-current-state re-audit confirms no new browser-direct or external `anon` dependency exists for the three RPCs.

## Group 3 preflight gate

Before creating a revoke migration, require all of the following against the then-current exact head and Production database:

- the three RPCs remain in both BFF authenticated allowlists and remain absent from public/login allowlists;
- forged browser `p_token` values are still overwritten by the HttpOnly cookie token on both platforms;
- unauthenticated calls still fail before the upstream RPC is called;
- server identity still requires `GROWTHOPS_SUPABASE_SECRET_KEY` and has no publishable-key fallback;
- P3/P4 `user_management_session_workspace_guards` is PASS;
- each function still resolves through `crm_session_context`, remains workspace-bound, and retains the intended ADMIN guard;
- `crm_upsert_user` still enforces password/role/last-admin/session-revocation protections;
- `crm_delete_user` still rejects self-delete and last-admin deletion;
- service_role EXECUTE remains present;
- authenticated EXECUTE remains absent;
- no unrelated Production fingerprint change has occurred.

## Intended later privilege change

Only after the predecessor and preflight gates pass, a dedicated later migration may revoke `anon` EXECUTE from exactly the three functions above while preserving `service_role` EXECUTE. The actual SQL is intentionally not present in this preparation branch.

If Group 2 has already reduced the total anon-executable CRM RPC count from 10 to 9 and no unrelated privilege change occurs, successful Group 3 completion would reduce that count from 9 to 6.

The later migration must ship with an exact inverse rollback and a read-only post-change check. A failure of authenticated CRM user administration on either exact-head Preview is a rollback trigger.

## Non-goals

This preparation branch does not change:

- `crm_login_v3` or `crm_public_status`;
- load/save/logout state RPCs;
- credential safe-summary, unlock, or scalar reveal behavior;
- database functions, grants, tables, RLS, policies, Vault, session duration, CSP, WAF, DNS, or CRM UI/business behavior;
- Group 1 or Group 2 branch heads.

Keeping Group 3 as a cohesive ADMIN user-management unit gives a small deterministic later rollback surface without mixing it with login, general state persistence, or credential summary behavior.
