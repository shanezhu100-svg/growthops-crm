# P5 Group 5 — Session / Workspace State Privilege Hardening

Last updated: 2026-08-23

## Status

Groups 1–4 predecessor gates are complete. Group 5 Production execution is complete and verified. The only Production privilege change was removal of `anon` EXECUTE from exactly three server-mediated session/workspace-state RPCs.

This branch is based directly on accepted `main@385bff8e0316bf8b1460b12202ea88f8c880a2c4` pending final evidence-head merge.

## Exact scope

- `crm_load_state_v3(text)`
- `crm_save_state(text,jsonb,bigint)`
- `crm_logout(text)`

## Accepted predecessor baseline

Immediately before Group 5, Production was verified as:

- `main`: `385bff8e0316bf8b1460b12202ea88f8c880a2c4`;
- CRM functions: `40`;
- anon EXECUTE: `5`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- RLS: `9/9`;
- latest migration: `20260823071407 / p5_group4_revoke_safe_summary_anon_exec`;
- canonical fingerprint: `258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`.

All three exact targets were `anon=true`, `authenticated=false`, `service_role=true`, and `PUBLIC EXECUTE=false`.

## Preserved runtime/database invariants

### `crm_load_state_v3`

The function still wraps state load and applies secret redaction. The underlying state path remains session/workspace scoped.

### `crm_save_state`

The live function still contains session-context enforcement, optimistic revision handling, state redaction, role-aware secret handling, Vault-backed secret extraction/write safeguards, and server audit logging.

### `crm_logout`

The function deliberately does not require `crm_session_context`; it hashes `p_token` and deletes only the matching CRM session. Both BFFs clear `__Host-growthops_crm` on logout success and upstream failure.

No CRM business data, session token, or Vault plaintext was read during Group 5 preflight/post-checks.

## BFF boundary

Both Vercel and Cloudflare continue to classify all three RPCs as authenticated-only. Missing HttpOnly session cookie returns `401 SESSION_REQUIRED` before upstream contact. Browser-supplied `p_token` is replaced by the server-read cookie token. Same-origin enforcement and server `sb_secret_` identity remain mandatory.

## Preparation evidence

Preparation head:

`6a19a63fc39a1536617dec6db33710342bbdd035`

Vercel preparation deployment:

- `dpl_Bcc1evu3q5LqNosYwm2yPLZVdY7k`
- READY
- Group 5 candidate/BFF PASS
- predecessor and P3/P4 gates PASS

Cloudflare preparation deployment:

- `4905e9f1-0957-4cfc-a332-79af7279e40e`
- `https://4905e9f1.growthops-crm.pages.dev/`
- success
- Group 5 candidate/BFF PASS
- P3/P4 attack regression PASS
- P1 parity PASS

## Execution-package exact-head evidence

Execution-package head:

`1068d5ba4c603f64b34ca99c6257718e268f9e1e`

Vercel:

- deployment `dpl_HWTZvqWfWW4gCGX8RjrMLwEMxPqt`;
- state `READY`;
- `P5_GROUP5_SESSION_STATE_CANDIDATE_OK` PASS;
- `P5_GROUP5_SESSION_STATE_BFF_OK` PASS;
- `P5_GROUP5_SESSION_STATE_REVOCATION_OK` PASS;
- predecessor Group 1–4 gates and P3/P4 attack regression PASS.

Cloudflare Pages:

- deployment `b5b3919a-9d3d-49a7-b2c9-b45fa2df8d05`;
- URL `https://b5b3919a.growthops-crm.pages.dev/`;
- status `success`;
- same exact commit `1068d5ba4c603f64b34ca99c6257718e268f9e1e`;
- Group 5 candidate/BFF/revocation gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Production migration

Forward migration file:

`supabase/migrations/20260823_p5_group5_revoke_session_state_anon_exec.sql`

Applied Production migration record:

`20260823085810 / p5_group5_revoke_session_state_anon_exec`

Exact privilege changes:

```sql
revoke execute on function public.crm_load_state_v3(text) from anon;
revoke execute on function public.crm_save_state(text, jsonb, bigint) from anon;
revoke execute on function public.crm_logout(text) from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group5_restore_session_state_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group5_session_state_anon_exec_check.sql`

## Production post-change verification

All three targets now have:

- `anon=false`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`.

Global Production state is now:

- CRM functions: `40`;
- anon EXECUTE: `2` (`5 -> 2`);
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- RLS: `9/9`;
- latest migration: `20260823085810 / p5_group5_revoke_session_state_anon_exec`;
- canonical fingerprint: `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`.

The only remaining anon-executable CRM RPCs are exactly:

- `crm_login_v3(text,text)`;
- `crm_public_status()`.

Those belong to Group 6 and were not modified by Group 5.

The canonical 258-line algorithm is the repository-frozen `supabase/baseline/p0_schema_security_fingerprint.sql`; the fingerprint delta is expected from exactly three `FPRIV` transitions.

## Automated gates

Expected markers:

`P5_GROUP5_SESSION_STATE_CANDIDATE_OK: load+save+logout=auth-only-bff; cookie-token=authoritative; save-secret-guard=covered; logout-distinction=preserved; group4=accepted; production-change=applied+verified`

`P5_GROUP5_SESSION_STATE_BFF_OK: load+save+logout=no-session-zero-upstream; cookie-token=authoritative; logout-success=clears-cookie; both-platforms=pass`

`P5_GROUP5_SESSION_STATE_REVOCATION_OK: revoke=3-session-state-anon-only; rollback=3-exact-grants; post-check=read-only; auth-bff=session-gated; expected-anon=2; service-role=40`

## Final merge gate

Before merging PR #25, the final evidence-only head must independently pass Vercel and Cloudflare with Group 1–5 gates, P3/P4 attack regression, and Cloudflare P1 parity green.

After merge, verify `main`, Vercel Production, Cloudflare Production, Production `40 / 2 / 0 / 40`, RLS `9/9`, latest migration `20260823085810`, remaining anon boundary exactly login/status, and canonical fingerprint `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`.

## Non-goals

Group 5 does not change function bodies, credential values, Vault contents, tables, RLS, session lifetime, login/public-status behavior, credential summary/reveal behavior, user-management behavior, UI business logic, or Group 6 privileges.
