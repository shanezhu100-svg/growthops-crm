# P5 Group 3 Candidate — Admin User-Management RPCs

Last updated: 2026-08-23

## Status

Preparation only. Group 1 and Group 2 predecessor gates are complete. This Group 3 branch is reconstructed directly onto accepted `main@92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b` and does **not** change Production database privileges at this checkpoint.

## Candidate scope

The cohesive candidate set is exactly:

- `crm_list_users(text)`
- `crm_upsert_user(text, uuid, text, text, text, text, boolean)`
- `crm_delete_user(text, uuid)`

No forward `REVOKE` migration is included yet. No rollback migration is included yet. No Group 3 SQL has been applied to Production.

## Accepted predecessor baseline

Group 2 is complete and merged. Current accepted baseline:

- `main`: `92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b`;
- CRM functions: `40`;
- anon EXECUTE: `9`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823062545 / p5_group2_revoke_legacy_credential_status_anon_exec`;
- canonical security fingerprint: `258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`.

## Why these RPCs form one later group

All three are live ADMIN user-management operations and intentionally remain reachable through the CRM server BFF. They are not dead-code retirement candidates.

The security boundary is server-mediated:

- both Vercel and Cloudflare `/api/crm` BFFs classify all three under authenticated RPCs, never public/login RPCs;
- the browser session token is held in the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- for authenticated RPCs the BFF overwrites any browser-supplied `p_token` with the cookie session token;
- both BFFs require the server-side `GROWTHOPS_SUPABASE_SECRET_KEY` identity and reject publishable-key fallback;
- same-origin checks run before RPC dispatch;
- safe logging does not log request args, passwords, session tokens, or secret keys;
- the P3/P4 database regression requires user-management functions to use `crm_session_context`, workspace scoping, and ADMIN guards.

## Group 3 preflight gate

Before creating a revoke migration, require all of the following against the exact current branch and Production state:

- all three RPCs remain in both BFF `AUTH_RPCS` sets and absent from `PUBLIC_RPCS` / `LOGIN_RPCS`;
- without the HttpOnly cookie each RPC returns `401 SESSION_REQUIRED` before any upstream call;
- with the cookie, any forged browser `p_token` is overwritten by the cookie token on both platforms;
- server identity still requires `GROWTHOPS_SUPABASE_SECRET_KEY` and has no publishable-key fallback;
- P3/P4 `user_management_session_workspace_guards` remains PASS;
- each function still resolves through `crm_session_context`, remains workspace-bound, and retains ADMIN authorization;
- `crm_upsert_user` still enforces password-length/role/self-disable/last-admin/password-change session-revocation safeguards;
- `crm_delete_user` still rejects self-delete and last-admin deletion;
- all three remain `anon=true`, `authenticated=false`, `service_role=true` before Group 3;
- no unrelated change has moved the accepted `40 / 9 / 0 / 40`, RLS `9/9`, or 258-line fingerprint baseline.

## Intended later privilege change

Only after the preflight passes may a dedicated Group 3 migration revoke `anon` EXECUTE from exactly the three functions above while preserving `service_role` EXECUTE.

Expected transition if no unrelated privilege change occurs:

- anon CRM EXECUTE: `9 -> 6`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

The later migration must ship with an exact inverse rollback and a read-only post-change check. A failure of authenticated CRM user administration on either exact-head Preview is a rollback trigger.

## Preparation-stage automated gate

`test_p5_group3_admin_user_mgmt_candidate.py` enforces:

- exact three-RPC scope;
- BFF authenticated-only classification;
- HttpOnly-cookie token authority and same-origin/server-secret boundary;
- executable Vercel + Cloudflare session-gate coverage for all three RPCs;
- existing P3/P4 database guard coverage;
- no Group 3 migration or rollback SQL appears during this preparation stage;
- accepted Group 2 baseline remains documented.

Expected marker:

`P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE_OK: admin-rpcs=auth-only-bff; cookie-token=authoritative; server-identity=required; db-guards=covered; group2=accepted; production-change=none`

## Non-goals

This preparation branch does not change `crm_login_v3`, `crm_public_status`, load/save/logout state RPCs, credential safe-summary/unlock/reveal behavior, database function bodies, grants, tables, RLS, policies, Vault, session duration, CSP, WAF, DNS, CRM UI/business behavior, or any Group 4–6 Production privilege.
