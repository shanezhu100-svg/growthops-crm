# Post-P5 service_role CRM RPC minimization

Last updated: 2026-08-23

## Status

Preparation only. Production change: none.

Accepted base is `main@9c4b0d8647da6f4544b563324a8d2c525165e74e` after P5 Groups 1–6 and residual audit-sequence ACL hardening.

Current Production baseline:

- CRM functions: `40`
- function EXECUTE boundary `PUBLIC / anon / authenticated / service_role = 0 / 0 / 0 / 40`
- CRM tables / RLS enabled: `9 / 9`
- audit sequence browser privileges: none; service_role SELECT/UPDATE/USAGE preserved
- latest migration: `20260823104232 / post_p5_revoke_browser_audit_sequence_acl`
- canonical fingerprint: `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`

## Why minimize service_role direct EXECUTE

Both hosting BFFs expose the same 11 server entry RPCs. The server credential therefore does not need direct PostgREST EXECUTE on every internal CRM helper. Internal function-to-function calls execute through postgres-owned SECURITY DEFINER chains or trigger execution and do not require a direct `service_role` grant on the callee.

The intended service-role surface becomes exactly 12 functions: the 11 BFF entries plus the recovery-only bootstrap function.

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

## Exact prepared change

`supabase/migrations/20260823_revoke_internal_service_role_exec.sql` revokes `service_role` EXECUTE from exactly 28 internal, trigger, helper, or legacy RPC functions. It changes no function body, table, sequence, RLS policy, browser-role grant, BFF allowlist, runtime asset, session rule, or credential behavior.

The exact inverse is:

`supabase/rollback/20260823_restore_internal_service_role_exec.sql`

The rollback restores service_role EXECUTE on exactly those same 28 signatures and nothing else.

## Important dependency note

`crm_reveal_client_secret_value_v5` currently calls `crm_reveal_client_secret_field_v3` internally. v3 therefore remains a database dependency and is **not dropped**. Only its direct service_role EXECUTE is proposed for removal. The same principle applies to the other internal helpers: object definitions stay intact; only direct server-role entry authority is reduced.

## Live transaction rehearsal — PASS and rolled back

A net-zero Production transaction was executed before preparing this branch:

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

No real credential, token, password, 2FA value, client data, or secret value was used or inspected in this rehearsal.

## Deterministic expected fingerprint

A second net-zero transaction temporarily applied the same 28 revokes, ran the repository's canonical `p0_schema_security_fingerprint.sql` algorithm, and rolled back.

Expected post-minimization state:

- inventory lines: `258`
- service_role EXECUTE: `12`
- canonical SHA-256: `625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`

The line count remains 258 because only `FPRIV` values change.

## Hard gates before any Production apply

1. Exact preparation head must build green on Vercel and Cloudflare.
2. All existing P3/P4, P5 Groups 1–6, credential, HttpOnly-session, P1 parity, and post-P5 sequence ACL gates must remain green.
3. Live read-only preflight must still show `0 / 0 / 0 / 40`, RLS `9/9`, sequence browser ACL none, migration `20260823104232`, and canonical `258 / 40aa990f...`.
4. Exactly 12 preserved service-role functions must be executable and exactly 28 revoke candidates must still be executable before apply.
5. No Production apply is permitted from a head whose scope has drifted beyond this permission-only package.

After any apply, the read-only post-check must show `0 / 0 / 0 / 12`, all 12 preserved functions executable, no other CRM function executable by service_role, sequence ACL unchanged, RLS `9/9`, and canonical `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`.

`production-change=none`
