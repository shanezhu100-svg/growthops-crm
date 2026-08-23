# P5 Group 6 Candidate — Login / Public Status Boundary

Last updated: 2026-08-23

## Status

Groups 1–5 are complete. Group 6 preparation preflight is complete and the exact two-RPC execution package is prepared. Production has not been changed by Group 6 yet.

This branch is reconstructed directly onto accepted `main@23b898ac6d7faaa79142e85e267ef7544a9c0b30`.

## Exact scope

- `crm_login_v3(text,text)`
- `crm_public_status()`

These are public application entry points and must continue working **without an existing CRM Session** through the same-origin server BFF after database anon revocation.

## Accepted predecessor baseline

- `main`: `23b898ac6d7faaa79142e85e267ef7544a9c0b30`;
- CRM functions: `40`;
- anon EXECUTE: `2`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- RLS: `9/9`;
- latest migration: `20260823085810 / p5_group5_revoke_session_state_anon_exec`;
- canonical fingerprint: `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`;
- remaining anon exactly `crm_login_v3(text,text)` and `crm_public_status()`.

## Public-entry invariants

### `crm_public_status()`

- only `PUBLIC_RPCS` member on both BFFs;
- no existing CRM Session required;
- incoming browser `p_token` stripped;
- upstream call uses server `sb_secret_` identity;
- response remains minimal: `initialized` + fixed service identifier;
- cache control remains `no-store`.

### `crm_login_v3(text,text)`

- only `LOGIN_RPCS` member on both BFFs;
- no existing CRM Session required;
- incoming browser `p_token` stripped;
- wraps service-only `crm_login` and redacts returned state;
- upstream token is removed from JSON and converted to the `__Host-growthops_crm` HttpOnly/Secure/SameSite=Strict cookie;
- missing token fails closed as `LOGIN_SESSION_MISSING`;
- invalid credentials remain generic `LOGIN_FAILED`.

## Internal login safeguards

The live service-only internal `crm_login` retains password hashing/verification, enabled-member checks, bounded login failure/throttle audit events, 10-minute pair/source thresholds, high-entropy session token generation, token hashing, role-view state scoping and successful-login audit behavior. Separate session gates continue to enforce the seven-day cap and maximum active sessions.

## Preparation exact-head evidence

Preparation head:

`ae9dddc184ff64a29889993ba8654ab442aa7249`

Vercel:

- deployment `dpl_AkEqRfjAavuDfJTh77Ty3Fve7RVK`;
- state `READY`;
- predecessor Group 1–5 gates PASS;
- `P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE_OK` PASS;
- `P5_GROUP6_PUBLIC_BOUNDARY_BFF_OK` PASS;
- P3/P4 attack regression PASS.

Cloudflare Pages:

- deployment `8817ca84-6f20-462f-8f4f-9b9b73c17b13`;
- URL `https://8817ca84.growthops-crm.pages.dev/`;
- status `success`;
- same exact commit `ae9dddc184ff64a29889993ba8654ab442aa7249`;
- Group 6 candidate/BFF gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Live Production preflight

Read-only Production preflight is **7/7 PASS**:

1. exact three-function inspection boundary found (`crm_login`, `crm_login_v3`, `crm_public_status`);
2. internal `crm_login` remains service-role-only;
3. `crm_login_v3` remains `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false`;
4. `crm_public_status` remains `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false`;
5. login wrapper still invokes internal login and redacts state;
6. internal password/audit/throttle/session safeguards remain present;
7. public status remains minimal and non-sensitive.

Global state remains `40 / 2 / 0 / 40`, RLS `9/9`, migration `20260823085810`, canonical fingerprint `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`.

No password, session token, workspace state, credential value, Vault plaintext, or other business data was read during the preflight.

## Prepared execution package

Forward migration:

`supabase/migrations/20260823_p5_group6_revoke_public_boundary_anon_exec.sql`

Exact revocations:

```sql
revoke execute on function public.crm_login_v3(text, text) from anon;
revoke execute on function public.crm_public_status() from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group6_restore_public_boundary_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group6_public_boundary_anon_exec_check.sql`

Static package gate:

`test_p5_group6_public_boundary_revocation.py`

Expected transition:

- anon CRM EXECUTE: `2 -> 0`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- CRM functions: remains `40`;
- RLS remains `9/9`.

## Pre-apply hard gate

Do not apply the migration until the current execution-package head independently passes Vercel and Cloudflare with Group 6 candidate/BFF/revocation gates, all predecessor gates, P3/P4 attack regression, and Cloudflare P1 parity.

Immediately before apply, re-lock Production to `main@23b898ac6d7faaa79142e85e267ef7544a9c0b30`, exact target privilege shape, `40 / 2 / 0 / 40`, RLS `9/9`, migration `20260823085810`, and canonical fingerprint `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`.

## Rollback triggers

Rollback restores only the two removed anon grants. Trigger rollback if either exact-head platform loses unauthenticated public status, login, HttpOnly cookie issuance, generic invalid-credential handling, same-origin protection, server-identity routing, or expected parity.

## Non-goals

Group 6 does not change usernames/passwords, credential values, session contents/lifetime, Vault contents, login thresholds, database function bodies, tables, RLS, policies, UI business logic, DNS, WAF, or unrelated grants.
