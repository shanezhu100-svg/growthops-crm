# Post-P5 service_role CRM RPC minimization

Last updated: 2026-08-23

## Status

Production change: applied and verified. PR remains Draft until the exact final evidence head is green on both hosting paths and the final Production freeze is repeated.

Accepted base is `main@9c4b0d8647da6f4544b563324a8d2c525165e74e` after P5 Groups 1–6 and residual audit-sequence ACL hardening.

Pre-apply Production baseline was:

- CRM functions: `40`
- function EXECUTE boundary `PUBLIC / anon / authenticated / service_role = 0 / 0 / 0 / 40`
- CRM tables / RLS enabled: `9 / 9`
- audit sequence browser privileges: none; service_role SELECT/UPDATE/USAGE preserved
- latest pre-apply migration: `20260823104232 / post_p5_revoke_browser_audit_sequence_acl`
- pre-apply canonical fingerprint: `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`

## Why minimize service_role direct EXECUTE

Both hosting BFFs expose the same 11 server entry RPCs. The server credential does not need direct PostgREST EXECUTE on every internal CRM helper. Internal function-to-function calls execute through postgres-owned SECURITY DEFINER chains or trigger execution and do not require a direct `service_role` grant on the callee.

The accepted direct service-role surface is exactly 12 functions: the 11 BFF entries plus the recovery-only bootstrap function.

### Preserved 11 BFF entry RPCs

- `crm_public_status()`
- `crm_login_v3(text,text)`
- `crm_load_state_v3(text)`
- `crm_save_state(text,jsonb,bigint)`
- `crm_logout(text)`
- `crm_list_users(text)`
- `crm_upsert_user(text,uuid,text,text,text,text,boolean)`
- `crm_delete_user(text,uuid)`
- `crm_client_account_safe_summary(text,text)`
- `crm_unlock_credentials_v1(text,text)`
- `crm_reveal_client_secret_value_v5(text,text,text,text,text,text)`

### Preserved recovery exception

- `crm_bootstrap_admin(text,text,text,text)`

Bootstrap is not a browser BFF entry. It is preserved as an operational/recovery function. Production is already initialized: bootstrap first checks for any existing `crm_users` row and raises `already_initialized`; browser roles have no EXECUTE on bootstrap. Keeping its service-role grant therefore preserves recovery capability without reopening the browser boundary.

## Exact change

`supabase/migrations/20260823_revoke_internal_service_role_exec.sql` revokes `service_role` EXECUTE from exactly 28 internal, trigger, helper, or legacy CRM functions. It changes no function body, table, sequence, RLS policy, browser-role grant, BFF allowlist, runtime asset, session rule, or credential behavior.

The exact inverse is:

`supabase/rollback/20260823_restore_internal_service_role_exec.sql`

The rollback restores service_role EXECUTE on exactly those same 28 signatures and nothing else.

## Important dependency note

`crm_reveal_client_secret_value_v5` currently calls `crm_reveal_client_secret_field_v3` internally. v3 remains a database dependency and is **not dropped**. Only its direct service_role EXECUTE was removed. The same principle applies to the other internal helpers: object definitions remain intact; only direct server-role entry authority was reduced.

## Pre-apply live transaction rehearsal — PASS and rolled back

A net-zero Production transaction was executed before apply:

1. `BEGIN`.
2. Temporarily revoke service_role EXECUTE from the same 28 functions.
3. Switch to `service_role` and invoke all 11 BFF entry RPCs with safe invalid test inputs.
4. Confirm public/login/logout reach their expected logic and all session-gated RPCs reach `INVALID_SESSION` rather than permission denial.
5. Measure the temporary permission surface.
6. `ROLLBACK`.

Observed rehearsal result:

- temporary service_role EXECUTE count: `12`
- preserved entry + bootstrap count: `12`
- unexpected direct service_role EXECUTE outside preserved set: `0`
- BFF-entry permission-denied tests: `0`
- Production after rollback: restored to service_role EXECUTE `40`

A second net-zero transaction temporarily applied the same 28 revokes, ran the repository canonical fingerprint algorithm, and rolled back. It predicted exactly:

- inventory lines: `258`
- service_role EXECUTE: `12`
- canonical SHA-256: `625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`

## Production result

Applied migration:

`20260823120150 / post_p5_minimize_service_role_rpc_exec`

Immediate read-only post-check matched the rehearsal exactly:

- CRM functions: `40`
- `PUBLIC EXECUTE = 0`
- `anon EXECUTE = 0`
- `authenticated EXECUTE = 0`
- `service_role EXECUTE = 12`
- preserved service-role entries: `12/12`
- unexpected service-role entries: `0`
- CRM tables / RLS: `9/9`
- audit sequence browser privileges: none
- audit sequence service_role SELECT/UPDATE/USAGE: preserved
- canonical fingerprint: `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`

## Post-apply functional smoke — PASS and rolled back

A transaction-local smoke test switched to `service_role` after the permanent revoke and then rolled back all test side effects.

Preserved wrappers:

- `crm_public_status()` -> `OK`
- `crm_login_v3(...)` with an intentionally invalid test identity -> wrapper executed (`OK` result path)
- `crm_load_state_v3(...)` with an invalid test session -> `INVALID_SESSION` (`P0001`), proving the wrapper entered its internal SECURITY DEFINER chain rather than failing permission checks

Direct internal calls now fail as intended:

- `crm_login(...)` -> `42501 permission denied`
- `crm_load_state(...)` -> `42501 permission denied`
- `crm_session_context(...)` -> `42501 permission denied`
- `crm_reveal_client_secret_field_v3(...)` -> `42501 permission denied`

No real credential, token, password, 2FA value, client data, or secret value was used or inspected in either rehearsal or smoke test.

## Final merge gates

1. Exact final evidence head must build green on Vercel and Cloudflare.
2. All existing P3/P4, P5 Groups 1–6, credential, HttpOnly-session, P1 parity, post-P5 sequence ACL, and service-role minimization gates must remain green.
3. Final Production freeze must still show `0 / 0 / 0 / 12`, RLS `9/9`, sequence browser ACL none, migration `20260823120150`, and canonical `258 / 625be29b...`.
4. PR may merge only at the exact verified head.

Rollback trigger: if any of the 11 BFF entry RPCs fails because an internal helper is no longer reachable through the intended SECURITY DEFINER chain, restore exactly the 28 service_role EXECUTE grants with the prepared rollback. Do not reopen PUBLIC/anon/authenticated execution.

`production-change=applied+verified`
