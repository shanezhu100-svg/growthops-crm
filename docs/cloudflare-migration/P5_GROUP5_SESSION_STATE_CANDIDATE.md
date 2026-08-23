# P5 Group 5 Candidate — Session / Workspace State RPCs

Last updated: 2026-08-23

## Status

Preparation only. Groups 1–4 predecessor gates are complete. This branch is reconstructed directly onto accepted `main@385bff8e0316bf8b1460b12202ea88f8c880a2c4` and does **not** change Production database privileges at this checkpoint.

## Candidate scope

Exactly three live authenticated RPCs:

- `crm_load_state_v3(text)`
- `crm_save_state(text,jsonb,bigint)`
- `crm_logout(text)`

These are core runtime operations, so a later anon revoke must preserve the same-origin BFF session boundary and each RPC's distinct database-side semantics.

No Group 5 forward `REVOKE` migration is included yet. No Group 5 rollback migration is included yet. No Group 5 SQL has been applied to Production.

## Accepted predecessor baseline

Group 4 is complete and merged. Current accepted Production baseline:

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
- the BFF clears the `__Host-growthops_crm` cookie on success and upstream failure.

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

## Group 5 preflight gate

Before creating a revoke migration, require exact-current-state evidence that:

1. both exact-head Vercel and Cloudflare builds are green;
2. the executable BFF harness proves no-session `401 + zero upstream`, authoritative cookie-token substitution, and logout cookie clearing on both platforms;
3. the final runtime still routes load/save/logout through the same-origin BFF;
4. live Production definitions retain the load redaction, save session/revision/role/Vault/audit safeguards, and intentional logout hash-delete behavior;
5. each target remains `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false`;
6. accepted global baseline remains `40 / 5 / 0 / 40`, RLS `9/9`, migration `20260823071407`, and fingerprint `258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`.

## Intended later privilege change

Only after the preflight passes may a dedicated Group 5 migration revoke `anon` EXECUTE from exactly the three functions above while preserving `service_role` EXECUTE.

Expected transition if no unrelated privilege change occurs:

- anon CRM EXECUTE: `5 -> 2`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

The two remaining anon-executable browser-boundary RPCs would be `crm_login_v3` and `crm_public_status`; they belong to Group 6 and must not be changed by Group 5.

## Rollback triggers

A later Group 5 change must have an exact inverse rollback. Roll back if either exact-head platform loses authenticated state load, safe state save/revision handling, role/secret restrictions, logout cookie clearing, or expected invalid-session behavior.

## Non-goals

This preparation branch does not change database functions, grants, tables, RLS, Vault contents, session lifetime, login/public-status behavior, credential summary/reveal behavior, user-management behavior, UI business logic, or Group 6 privileges.
