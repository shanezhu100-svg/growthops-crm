# P5 Group 6 Candidate — Login / Public Status Boundary

Last updated: 2026-08-23

## Status

Preparation only. Groups 1–5 are complete. This branch is reconstructed directly onto accepted `main@23b898ac6d7faaa79142e85e267ef7544a9c0b30` and does **not** change Production database privileges at this checkpoint.

## Candidate scope

Exactly the final two currently anon-executable CRM RPCs:

- `crm_login_v3(text,text)`
- `crm_public_status()`

These are deliberately different from Groups 2–5: they are public application entry points that must continue working **without an existing CRM Session**. A later database anon revoke is acceptable only because the browser no longer calls Supabase directly; both Cloudflare and Vercel BFFs call these RPCs with server `sb_secret_` identity.

No Group 6 forward `REVOKE` migration is included yet. No Group 6 rollback migration is included yet. No Group 6 SQL has been applied to Production.

## Accepted predecessor baseline

Group 5 is complete and merged. Current accepted Production baseline:

- `main`: `23b898ac6d7faaa79142e85e267ef7544a9c0b30`;
- CRM functions: `40`;
- anon EXECUTE: `2`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823085810 / p5_group5_revoke_session_state_anon_exec`;
- canonical security fingerprint: `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`;
- the only anon-executable CRM RPCs are exactly `crm_login_v3(text,text)` and `crm_public_status()`.

## Public-entry invariants

### `crm_public_status()`

- remains the only `PUBLIC_RPCS` member on both BFFs;
- does not require an existing CRM Session;
- browser-supplied `p_token` is deleted before the upstream call;
- live database output remains limited to `initialized` and the fixed service identifier;
- no user, workspace, credential, token, password, 2FA, Vault, or client data is returned.

### `crm_login_v3(text,text)`

- remains the only `LOGIN_RPCS` member on both BFFs;
- does not require an existing CRM Session;
- browser-supplied `p_token` is deleted before the upstream call;
- wraps the service-only internal `crm_login` and performs an additional `crm_redact_secrets` pass over returned workspace state;
- the BFF removes the returned session token from JSON, requires a non-empty token on success, and converts it into the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- login failure remains a generic `LOGIN_FAILED` browser response and must not reveal whether an account exists.

## Internal login protections that must remain intact

The service-only `crm_login` must continue to:

- normalize username keys and require enabled users/members;
- verify password with `extensions.crypt` against the stored password hash;
- return the same `INVALID_CREDENTIALS` result for bad credentials and throttled attempts;
- record bounded `LOGIN_FAILURE` / `LOGIN_THROTTLED` audit events without password/token/2FA/raw-IP/header dumps;
- enforce the current 10-minute pair/source thresholds;
- generate a high-entropy session token and store only its hash;
- scope returned workspace state through role-view logic;
- record successful `LOGIN` audit activity;
- remain service-role-only at the database privilege layer.

The separate session controls that cap actual session lifetime and active-session count must remain green as predecessor security gates.

## BFF invariants

For both public entry points:

- POST-only;
- same-origin / Fetch Metadata protection before dispatch;
- narrow exact RPC allowlists;
- `GROWTHOPS_SUPABASE_SECRET_KEY` matching `sb_secret_` with no publishable-key fallback;
- incoming browser `p_token` is never trusted;
- upstream errors are sanitized and request args/password/session tokens/secret keys are not logged;
- cache-control remains `no-store`.

## Group 6 preflight gate

Before creating a revoke migration, require exact-current-state evidence that:

1. exact-head Vercel and Cloudflare builds are green;
2. executable BFF tests prove public status and login work without an existing Session on both platforms;
3. forged `p_token` is stripped; login token is moved to the secure HttpOnly cookie; invalid login is generic; missing token fails closed; missing server identity fails before upstream; cross-origin is blocked;
4. the live database preflight is 7/7 PASS for internal login, login wrapper, public-status shape and login safeguards;
5. `crm_login_v3` and `crm_public_status` remain `anon=true`, `authenticated=false`, `service_role=true`, `PUBLIC=false` while internal `crm_login` remains service-role-only;
6. Production remains `40 / 2 / 0 / 40`, RLS `9/9`, migration `20260823085810`, and canonical fingerprint `258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb`.

## Intended later privilege change

Only after the preflight passes may a dedicated Group 6 migration revoke `anon` EXECUTE from exactly `crm_login_v3(text,text)` and `crm_public_status()` while preserving `service_role` EXECUTE.

Expected successful transition:

- anon CRM EXECUTE: `2 -> 0`;
- authenticated CRM EXECUTE: remains `0`;
- service_role CRM EXECUTE: remains `40`;
- total CRM functions: remains `40`.

The later migration must have an exact inverse rollback and read-only post-change verification. Loss of unauthenticated public status, successful login, HttpOnly cookie issuance, generic invalid-credential behavior, or exact-head Cloudflare/Vercel parity is a rollback trigger.

## Non-goals

This preparation branch does not change usernames/passwords, credential values, session contents, Vault contents, login thresholds, database function bodies, grants, tables, RLS, policies, UI business logic, DNS, WAF, or `main`.
