# P5 Group 3 — Admin User-Management RPC Privilege Hardening

Last updated: 2026-08-23

## Status

Group 1 and Group 2 predecessor gates are complete. Group 3 live preflight is PASS. **Execution package is prepared but not applied to Production.**

This branch is based directly on accepted `main@92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b`.

## Exact scope

Group 3 contains exactly these three live ADMIN user-management RPCs:

- `crm_list_users(text)`
- `crm_upsert_user(text, uuid, text, text, text, text, boolean)`
- `crm_delete_user(text, uuid)`

They remain intentionally reachable through the authenticated server BFF path. Group 3 removes only the transitional direct `anon` EXECUTE grants; it does not remove the BFF path or alter any function body.

## Accepted predecessor baseline

Current accepted Production baseline after Group 2:

- `main`: `92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b`;
- CRM functions: `40`;
- anon EXECUTE: `9`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823062545 / p5_group2_revoke_legacy_credential_status_anon_exec`;
- canonical fingerprint: `258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`.

## BFF/runtime boundary

Both Vercel and Cloudflare `/api/crm` BFFs:

- keep all three RPCs in `AUTH_RPCS` and out of `PUBLIC_RPCS` / `LOGIN_RPCS`;
- require the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- reject missing cookie with `401 SESSION_REQUIRED` before any upstream RPC call;
- overwrite any browser-supplied `p_token` with the server-read cookie token;
- require `GROWTHOPS_SUPABASE_SECRET_KEY` with `sb_secret_` identity and have no publishable-key fallback;
- enforce same-origin before dispatch;
- keep request secrets out of logs and responses.

The cross-platform P2-B harness dynamically executes all three ADMIN RPC cases against both handlers and proves the missing-cookie and forged-token behavior.

## Production function preflight

Live read-only inspection confirms all three functions are `SECURITY DEFINER` and currently have the same explicit ACL shape:

- `anon=true`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`.

All three call `crm_session_context`, are workspace-bound, and require ADMIN authorization.

`crm_upsert_user` retains:

- minimum 10-character password requirement for new users;
- role allowlist (`ADMIN`, `FINANCE`, `OPS`, `SALES`);
- duplicate-username protection;
- self-disable prevention;
- last-active-admin protection;
- bcrypt password hashing;
- session revocation after password changes while preserving the caller's current session only for self password change;
- server audit logging.

`crm_delete_user` retains:

- self-delete prevention;
- workspace membership check;
- last-active-admin protection;
- server audit logging.

No real user write operation was performed during this preflight.

## Preparation exact-head evidence

Preflight head: `5fc74065e64c0b99e7a0920d291c1323b3ffd5b6`.

Vercel:

- deployment `dpl_6UW8jGBR5k9YsN9wYsW9XmyfrNAv`;
- state `READY`;
- cross-platform marker includes `admin-user-rpcs=session-gated`;
- `P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE_OK` PASS;
- Group 1/2 and P3/P4 gates remain PASS.

Cloudflare Pages:

- deployment `a208a12f-6801-458e-846d-e60444609669`;
- URL `https://a208a12f.growthops-crm.pages.dev/`;
- status `success`;
- same Group 3 candidate and cross-platform session gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Prepared execution package

Forward migration:

`supabase/migrations/20260823_p5_group3_revoke_admin_user_mgmt_anon_exec.sql`

It contains exactly three statements:

```sql
revoke execute on function public.crm_list_users(text) from anon;
revoke execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) from anon;
revoke execute on function public.crm_delete_user(text, uuid) from anon;
```

Exact inverse rollback:

`supabase/rollback/20260823_p5_group3_restore_admin_user_mgmt_anon_exec.sql`

Read-only post-check:

`supabase/baseline/p5_group3_admin_user_mgmt_anon_exec_check.sql`

Dedicated static gate:

`test_p5_group3_admin_user_mgmt_revocation.py`

Expected privilege transition after a later Production apply:

- anon CRM EXECUTE: `9 -> 6`;
- authenticated CRM EXECUTE: `0`;
- service_role CRM EXECUTE: `40`;
- CRM functions: `40`.

## Execution gate

Before applying Production, the new execution-package exact head must independently pass Vercel and Cloudflare builds, including:

- Group 1/2 gates;
- P3/P4 attack regression;
- dynamic three-ADMIN-RPC session gate;
- `P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE_OK`;
- `P5_GROUP3_ADMIN_USER_MGMT_REVOCATION_OK`;
- Cloudflare P1 output parity.

Immediately before apply, Production must still match `40 / 9 / 0 / 40`, RLS `9/9`, migration `20260823062545`, and fingerprint `258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`.

## Non-goals

Group 3 does not alter `crm_login_v3`, `crm_public_status`, load/save/logout state RPCs, credential safe-summary/unlock/reveal behavior, any database function body, tables, RLS, policies, Vault, session duration, CSP, WAF, DNS, CRM UI/business behavior, or Groups 4–6 privileges.
