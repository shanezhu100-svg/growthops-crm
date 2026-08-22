# P5 Group 5 Candidate — Session / Workspace State RPCs

Last updated: 2026-08-22

## Status

Preparation only. This stacked branch does **not** change Production database privileges. It is intentionally based on P5 Group 4 and must not advance ahead of Groups 1–4.

## Candidate scope

Exactly three live authenticated RPCs:

- `crm_load_state_v3(text)`
- `crm_save_state(text,jsonb,bigint)`
- `crm_logout(text)`

These are core runtime operations, so a later anon revoke must preserve the same-origin BFF session boundary and each RPC's distinct database-side semantics.

No Group 5 forward `REVOKE` migration is included yet. No Group 5 rollback migration is included yet. No SQL is applied to Production by this preparation branch.

## Distinct database invariants

### `crm_load_state_v3`

- wraps `crm_load_state(p_token)`;
- `crm_load_state` resolves `crm_session_context(p_token)` and scopes reads by the session workspace;
- role-view state is applied before the wrapper performs an additional `crm_redact_secrets` pass;
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
- the BFF must clear the `__Host-growthops_crm` cookie even when logout upstream fails, preventing a stale browser session from being retained.

The logout difference is intentional and must not be incorrectly normalized into a direct-session-context requirement.

## BFF invariants

For all three RPCs on both Vercel and Cloudflare:

- they remain authenticated-only, never public/login;
- no HttpOnly cookie means `401 SESSION_REQUIRED` before upstream RPC contact;
- with a cookie, any browser-supplied `p_token` is overwritten with the server-read cookie token;
- same-origin enforcement remains active;
- only server `GROWTHOPS_SUPABASE_SECRET_KEY` / `sb_secret_` identity is accepted;
- error responses remain sanitized and request args/tokens are not logged.

For logout specifically, the browser cookie must be cleared on both success and upstream failure.

## Required predecessor gates

Do not create or apply a Group 5 revoke migration until Groups 1–4 have each completed their own required acceptance, rollback verification, merge, and post-merge Production/fingerprint verification. Group 4 must also have current exact-head Cloudflare + Vercel green evidence.

After predecessors land, Group 5 must repeat the live database function-source and privilege audit, exact-head BFF regression, real authenticated load/save/logout acceptance on both rollback platforms, and only then author a dedicated exact-three-RPC migration/rollback/check.

## Intended later privilege change

Only after all predecessor and Group 5 preflight gates pass, a dedicated later migration may revoke `anon` EXECUTE from exactly the three functions above while preserving `service_role` EXECUTE.

If Groups 2–4 have completed with no unrelated privilege changes, the expected anon-executable CRM RPC count immediately before Group 5 would be 5 and after Group 5 would be 2. The two remaining public-boundary RPCs would be `crm_login_v3` and `crm_public_status` and must be handled separately.

## Rollback triggers

A later Group 5 change must have an exact inverse rollback. Roll back if either exact-head platform loses any of:

- authenticated state load;
- safe state save / revision handling;
- role-based state restrictions or secret redaction;
- logout cookie clearing;
- expected Session-invalid behavior.

## Non-goals

This preparation branch does not change database functions, grants, tables, RLS, Vault contents, Session lifetime, login/public-status behavior, credential summary/reveal behavior, user-management behavior, UI business logic, predecessor branch heads, or `main`.
