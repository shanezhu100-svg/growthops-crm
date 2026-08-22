# P5 Group 6 Candidate — Login / Public Status Boundary

Last updated: 2026-08-22

## Status

Preparation only. This stacked branch does **not** change Production database privileges. It is intentionally based on P5 Group 5 and must not advance ahead of Groups 1–5.

## Candidate scope

Exactly the final two currently anon-executable CRM RPCs, **conditional on Groups 2–5 having landed first**:

- `crm_login_v3(text,text)`
- `crm_public_status()`

These are deliberately different from Groups 2–5: they are public application entry points that must continue working **without an existing CRM Session**. A later database anon revoke is acceptable only because the browser no longer calls Supabase directly; both Cloudflare and Vercel BFFs call the RPCs with server `sb_secret_` identity.

No Group 6 forward `REVOKE` migration is included yet. No Group 6 rollback migration is included yet. No SQL is applied to Production by this preparation branch.

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
- verify the password with `extensions.crypt` against the stored password hash;
- return the same `INVALID_CREDENTIALS` result for bad credentials and throttled attempts;
- record `LOGIN_FAILURE` audit events without password/token/2FA/raw-IP/header dumps;
- derive only a truncated SHA-256 source bucket from the proxy source IP when available;
- enforce the current conservative 10-minute thresholds (username/source pair and source-wide) and record bounded `LOGIN_THROTTLED` audit events;
- generate a high-entropy session token and store only its hash;
- scope the returned workspace state through role-view logic;
- write a successful `LOGIN` audit event;
- continue to be service-role-only at the database privilege layer.

The separate database trigger/session controls that cap actual session lifetime and active-session count must remain green as predecessor security gates.

## BFF invariants for both public entry points

- POST-only endpoint;
- same-origin / Fetch Metadata protection remains active before dispatch;
- exact RPC allowlists remain narrow;
- server configuration requires `GROWTHOPS_SUPABASE_SECRET_KEY` matching `sb_secret_` and has no publishable-key fallback;
- neither public path trusts an incoming browser `p_token`;
- upstream errors are sanitized and request args/password/session tokens/secret keys are not logged;
- cache-control remains `no-store`.

## Required predecessor gates

Do not create or apply a Group 6 revoke migration until, in order:

1. P5 Group 1 / PR #21 completes real authenticated Cloudflare + Vercel acceptance, ADMIN unlock/reveal acceptance, expected-head merge, and post-merge Production verification;
2. P5 Group 2 / PR #22 completes its one-RPC retirement, rollback verification, merge, and Production fingerprint verification;
3. P5 Group 3 / PR #23 completes ADMIN user-management retirement, rollback verification, merge, and Production fingerprint verification;
4. P5 Group 4 / PR #24 completes safe-summary retirement, rollback verification, merge, and Production fingerprint verification;
5. P5 Group 5 / PR #25 completes session-state retirement, rollback verification, merge, and Production fingerprint verification;
6. Group 6 re-runs exact-current-state Cloudflare + Vercel public-entry tests and live database preflight.

## Intended later privilege change

Only after all predecessors and Group 6 preflight gates pass, a dedicated later migration may revoke `anon` EXECUTE from exactly `crm_login_v3(text,text)` and `crm_public_status()` while preserving `service_role` EXECUTE.

If Groups 2–5 complete with no unrelated privilege changes, the expected anon-executable CRM RPC count immediately before Group 6 is 2. Successful Group 6 completion should reduce that count to 0 while keeping browser login/public-status behavior operational through the same-origin server BFF.

The later migration must have an exact inverse rollback and a read-only post-change check. Any loss of unauthenticated public status, successful login, HttpOnly cookie issuance, generic invalid-credential behavior, or exact-head Cloudflare/Vercel parity is a rollback trigger.

## Non-goals

This preparation branch does not change usernames/passwords, credential values, Session contents, Vault contents, login thresholds, database functions, grants, tables, RLS, policies, UI business logic, DNS, WAF, predecessor branch heads, or `main`.
