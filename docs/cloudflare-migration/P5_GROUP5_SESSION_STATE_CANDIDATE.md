# P5 Group 5 Candidate — Session / Workspace State RPCs

Last updated: 2026-08-23

## Status

Groups 1–4 predecessor gates are complete. Group 5 preflight is complete and the exact three-RPC execution package is prepared. Production has not been changed by Group 5 yet.

This branch is reconstructed directly onto accepted `main@385bff8e0316bf8b1460b12202ea88f8c880a2c4`.

## Candidate scope

Exactly three live authenticated RPCs:

- `crm_load_state_v3(text)`
- `crm_save_state(text,jsonb,bigint)`
- `crm_logout(text)`

These are core runtime operations, so the later anon revoke must preserve the same-origin BFF session boundary and each RPC's distinct database-side semantics.

## Accepted predecessor baseline

Group 4 is complete and merged. Accepted Production baseline immediately before Group 5:

- `main`: `385bff8e0316bf8b1460b12202ea88f8c880a2c4`;
- CRM functions: `40`;
- anon EXECUTE: `5`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823071407 / p5_group4_revoke_safe_summary_anon_exec`;
- canonical security fingerprint: `258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`.

## Distinct database invariants

### `crm_load_state_v3`

- wraps `crm_load_state(p_token)`;
- the underlying state load resolves `crm_session_context(p_token)` and scopes reads by the session workspace;
- the v3 wrapper performs an additional `crm_redact_secrets` pass;
- returned state must remain free of live credential plaintext.

### `crm_save_state`

- resolves `crm_session_context(p_token)` and locks the current workspace state row;
- enforces optimistic revision conflict detection;
- redacts incoming/public state and restores role-restricted fields;
- only ADMIN may contribute extracted live-secret updates;
- prunes/writes Vault-backed secret state separately from public workspace state;
- records a server audit event.

### `crm_logout`

- deliberately does not require `crm_session_context`;
- deletes only the session row whose stored hash matches `crm_token_hash(p_token)`;
- the BFF clears the `__Host-growthops_crm` cookie on success and upstream failure.

The logout difference is intentional and must not be incorrectly normalized into a direct-session-context requirement.

## BFF invariants

For all three RPCs on both Vercel and Cloudflare:

- they are authenticated-only, never public/login;
- no HttpOnly cookie means `401 SESSION_REQUIRED` before upstream RPC contact;
- with a cookie, any browser-supplied `p_token` is overwritten with the server-read cookie token;
- same-origin enforcement remains active;
- only server `GROWTHOPS_SUPABASE_SECRET_KEY` / `sb_secret_` identity is accepted;
- error responses remain sanitized and request args/tokens are not logged.

For logout specifically, the browser cookie is cleared on both success and upstream failure.

## Preparation exact-head evidence

Preparation head:

`6a19a63fc39a1536617dec6db33710342bbdd035`

Vercel:

- deployment `dpl_Bcc1evu3q5LqNosYwm2yPLZVdY7k`;
- state `READY`;
- Group 1–4 gates PASS;
- `P5_GROUP5_SESSION_STATE_CANDIDATE_OK` PASS;
- `P5_GROUP5_SESSION_STATE_BFF_OK` PASS;
- P3/P4 attack regression PASS, including logout upstream-failure cookie clearing.

Cloudflare Pages:

- deployment `4905e9f1-0957-4cfc-a332-79af7279e40e`;
- URL `https://4905e9f1.growthops-crm.pages.dev/`;
- status `success`;
- same exact commit `6a19a63fc39a1536617dec6db33710342bbdd035`;
- Group 5 candidate/BFF gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Live Production preflight

Read-only database inspection confirmed every target is currently:

- `anon=true`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`.

It also confirmed:

- `crm_load_state_v3` still wraps the state loader and applies secret redaction;
- `crm_save_state` still contains session context, revision, redaction, live-secret extraction/Vault handling, and server-audit safeguards;
- `crm_logout` still intentionally omits session-context resolution and deletes only the token-hash-matched session;
- global state remains `40 / 5 / 0 / 40`, RLS `9/9`, latest migration `20260823071407`.

No CRM business state, session token, or Vault plaintext was read during this preflight.

## Prepared execution package

Forward migration:

`supabase/migrations/20260823_p5_group5_revoke_session_state_anon_exec.sql`

It contains exactly three anon EXECUTE revocations:

```sql
revoke execute on function public.crm_load_state_v3(text) from anon;
revoke execute on function public.crm_save_state(text, jsonb, bigint) from anon;
revoke execute on function public.crm_logout(text) from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group5_restore_session_state_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group5_session_state_anon_exec_check.sql`

Static package gate:

`test_p5_group5_session_state_revocation.py`

Expected transition if no unrelated privilege change occurs:

- anon CRM EXECUTE: `5 -> 2`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

The two remaining anon-executable browser-boundary RPCs must be exactly `crm_login_v3` and `crm_public_status`; they belong to Group 6 and must not be changed by Group 5.

## Pre-apply hard gate

Do not apply the Group 5 migration until the current execution-package head independently passes both Vercel and Cloudflare with:

- Group 5 candidate gate;
- Group 5 BFF gate;
- Group 5 revocation package gate;
- predecessor Group 1–4 gates;
- P3/P4 attack regression;
- Cloudflare P1 output parity.

Immediately before apply, re-lock Production to the accepted `main`, exact three target grants, `40 / 5 / 0 / 40`, RLS `9/9`, migration `20260823071407`, and canonical fingerprint `258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`.

## Rollback triggers

Roll back if either exact-head platform loses authenticated state load, safe state save/revision handling, role/secret restrictions, logout cookie clearing, or expected invalid-session behavior. The inverse rollback restores only the three removed anon grants.

## Non-goals

Group 5 does not change function bodies, credential values, Vault contents, tables, RLS, session lifetime, login/public-status behavior, credential summary/reveal behavior, user-management behavior, UI business logic, or Group 6 privileges.
