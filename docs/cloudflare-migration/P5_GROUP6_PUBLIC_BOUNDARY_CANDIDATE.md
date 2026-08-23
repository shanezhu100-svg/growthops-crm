# P5 Group 6 — Login / Public Status Privilege Hardening

Last updated: 2026-08-23

## Status

Groups 1–5 predecessor gates are complete. Group 6 Production execution is complete and verified. P5's transitional CRM `anon` EXECUTE surface is now fully retired: `40 / 0 / 0 / 40` for CRM functions while browser public entry remains routed through the same-origin server BFF using service identity.

This branch is based directly on accepted `main@23b898ac6d7faaa79142e85e267ef7544a9c0b30` pending final evidence-head merge.

## Exact Group 6 scope

- `crm_login_v3(text,text)`
- `crm_public_status()`

These remain public application entry points at the **BFF layer**, but are no longer executable by the Supabase `anon` database role.

## Accepted predecessor baseline

Immediately before Group 6, Production was verified as:

- `main`: `23b898ac6d7faaa79142e85e267ef7544a9c0b30`;
- CRM functions: `40`;
- anon EXECUTE: `2`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- RLS: `9/9`;
- latest migration: `20260823085810 / p5_group5_revoke_session_state_anon_exec`;
- canonical fingerprint: `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`;
- only remaining anon RPCs: `crm_login_v3(text,text)` and `crm_public_status()`.

Both targets were `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false` before Group 6 execution.

## Preserved public-entry boundary

### `crm_public_status()`

Both BFFs keep it as the sole `PUBLIC_RPCS` member. It requires no existing CRM Session, strips incoming browser `p_token`, calls Supabase with server `sb_secret_` identity, returns the minimal initialized/service shape, and remains `no-store`.

### `crm_login_v3(text,text)`

Both BFFs keep it as the sole `LOGIN_RPCS` member. It requires no existing CRM Session, strips incoming browser `p_token`, calls Supabase through server identity, strips the returned session token from JSON, requires a non-empty token, and converts the token to `__Host-growthops_crm` with HttpOnly, Secure, SameSite=Strict and the seven-day browser lifetime. Invalid credentials remain generic and a malformed success without a token fails closed.

The internal service-only `crm_login` continues to retain password verification, login audit/throttle controls, token hashing, role-view state scoping, and session safeguards.

## Preparation evidence

Preparation head:

`ae9dddc184ff64a29889993ba8654ab442aa7249`

Vercel:
- deployment `dpl_AkEqRfjAavuDfJTh77Ty3Fve7RVK`;
- READY;
- Group 6 candidate/BFF PASS;
- predecessor and P3/P4 gates PASS.

Cloudflare:
- deployment `8817ca84-6f20-462f-8f4f-9b9b73c17b13`;
- URL `https://8817ca84.growthops-crm.pages.dev/`;
- success;
- Group 6 candidate/BFF PASS;
- P3/P4 attack regression PASS;
- P1 parity PASS.

Live Production preparation preflight was 7/7 PASS, including exact function boundary, service-only internal login, pre-revoke target grants, wrapper redaction, internal login safeguards, and minimal public-status shape.

## Execution-package exact-head evidence

Execution-package head:

`2b8b24bf8cec94ef9a66fdef5581a29f0afe96e1`

Vercel:
- deployment `dpl_Bv1hCwK7me9ijVz6fjMX2pu7vTHa`;
- READY;
- `P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE_OK` PASS;
- `P5_GROUP6_PUBLIC_BOUNDARY_BFF_OK` PASS;
- `P5_GROUP6_PUBLIC_BOUNDARY_REVOCATION_OK` PASS;
- predecessor Group 1–5 gates and P3/P4 attack regression PASS.

Cloudflare:
- deployment `a7c92876-ad57-4d9c-87a0-bfa271593be9`;
- URL `https://a7c92876.growthops-crm.pages.dev/`;
- success;
- same exact commit `2b8b24bf8cec94ef9a66fdef5581a29f0afe96e1`;
- Group 6 candidate/BFF/revocation gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Production migration

Forward migration file:

`supabase/migrations/20260823_p5_group6_revoke_public_boundary_anon_exec.sql`

Applied Production migration:

`20260823101656 / p5_group6_revoke_public_boundary_anon_exec`

Exact privilege changes:

```sql
revoke execute on function public.crm_login_v3(text, text) from anon;
revoke execute on function public.crm_public_status() from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group6_restore_public_boundary_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group6_public_boundary_anon_exec_check.sql`

## Production post-change verification

Both targets now have:

- `anon=false`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`.

Global Production state is now:

- CRM functions: `40`;
- anon EXECUTE: `0` (`2 -> 0`);
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- RLS: `9/9`;
- remaining anon-executable CRM RPCs: none;
- latest migration: `20260823101656 / p5_group6_revoke_public_boundary_anon_exec`;
- canonical fingerprint: `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`.

The repository-frozen canonical inventory remains exactly 258 lines. The expected fingerprint delta is exactly two `FPRIV` transitions from `anon=true` to `anon=false`.

No password, session token, credential value, workspace state, Vault plaintext, or other CRM business data was read during the privilege audit or post-check.

## Automated gates

Expected markers:

`P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE_OK: public-status=no-session-public; login=no-session-cookie-bridge; server-identity=required; login-guards=preserved; preflight=read-only; group5=accepted; production-change=applied+verified`

`P5_GROUP6_PUBLIC_BOUNDARY_BFF_OK: public-status=no-session+server-identity; login=no-session+token-to-HttpOnly-cookie; forged-token=stripped; invalid-login=generic; cross-origin=blocked; both-platforms=pass`

`P5_GROUP6_PUBLIC_BOUNDARY_REVOCATION_OK: revoke=2-public-boundary-anon-only; rollback=2-exact-grants; post-check=read-only; bff=no-session-server-bridge; expected-anon=0; service-role=40`

## Final merge gate

Before merging PR #26, the final evidence-only head must independently pass Vercel and Cloudflare with Group 1–6 gates, P3/P4 attack regression, and Cloudflare P1 parity green.

After merge, verify `main`, Vercel Production, Cloudflare Production, Production `40 / 0 / 0 / 40`, RLS `9/9`, latest migration `20260823101656`, no remaining anon CRM function execution, and canonical fingerprint `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`.

## Non-goals

Group 6 does not change usernames/passwords, credential values, session contents/lifetime, Vault contents, login thresholds, database function bodies, tables, RLS, policies, UI business logic, DNS, WAF, or unrelated grants.
