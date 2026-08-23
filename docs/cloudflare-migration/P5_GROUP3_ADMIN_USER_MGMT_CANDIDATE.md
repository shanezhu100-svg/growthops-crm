# P5 Group 3 — Admin User-Management RPC Privilege Hardening

Last updated: 2026-08-23

## Status

Group 1 and Group 2 predecessor gates are complete. Group 3 Production execution is complete and verified. The only database privilege change was removal of `anon` EXECUTE from exactly three server-mediated ADMIN user-management RPCs.

The branch remains based on accepted `main@92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b` pending the final evidence-head merge.

## Exact scope

Group 3 contains exactly:

- `crm_list_users(text)`
- `crm_upsert_user(text, uuid, text, text, text, text, boolean)`
- `crm_delete_user(text, uuid)`

The authenticated BFF path remains intact. No function body, user row, table, RLS policy, Vault value, session rule, or CRM business behavior was changed by the Group 3 migration.

## Accepted predecessor baseline

Immediately before Group 3, Production was verified as:

- `main`: `92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b`;
- CRM functions: `40`;
- anon EXECUTE: `9`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823062545 / p5_group2_revoke_legacy_credential_status_anon_exec`;
- canonical fingerprint: `258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`.

All three target functions were `SECURITY DEFINER` with explicit `anon` and `service_role` grants, no `authenticated` grant, and no PUBLIC EXECUTE.

## BFF/runtime boundary

Both Vercel and Cloudflare `/api/crm` BFFs continue to:

- keep all three RPCs in `AUTH_RPCS` and out of `PUBLIC_RPCS` / `LOGIN_RPCS`;
- require the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- reject missing cookie with `401 SESSION_REQUIRED` before any upstream RPC call;
- overwrite browser-supplied `p_token` with the server-read cookie token;
- require `GROWTHOPS_SUPABASE_SECRET_KEY` with `sb_secret_` identity and no publishable-key fallback;
- enforce same-origin before dispatch;
- keep request secrets out of logs and responses.

The executable cross-platform P2-B harness covers all three ADMIN RPCs with fake upstream data only; no real user administration operation was performed for testing.

## Function safeguards verified before execution

All three functions call `crm_session_context`, are workspace-bound, and require ADMIN authorization.

`crm_upsert_user` retains minimum password length, role allowlist, duplicate-username protection, self-disable prevention, last-active-admin protection, bcrypt password hashing, password-change session revocation, and server audit logging.

`crm_delete_user` retains self-delete prevention, workspace membership validation, last-active-admin protection, and server audit logging.

## Execution package exact-head evidence

Execution-package head:

`803ae738d059071b0f906732af2e45a257e8ec63`

Vercel:

- deployment `dpl_A57fwk1g9HUyW7FTn9LTeXFiANVG`;
- state `READY`;
- `admin-user-rpcs=session-gated` PASS;
- `P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE_OK` PASS;
- `P5_GROUP3_ADMIN_USER_MGMT_REVOCATION_OK` PASS;
- Group 1/2 and P3/P4 gates remain PASS.

Cloudflare Pages:

- deployment `5e9ddffb-582b-4d7c-b514-1ca3e8e8fba6`;
- URL `https://5e9ddffb.growthops-crm.pages.dev/`;
- status `success`;
- same exact commit `803ae738d059071b0f906732af2e45a257e8ec63`;
- dynamic ADMIN session gate PASS;
- Group 3 candidate/revocation gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Production migration

Forward migration file:

`supabase/migrations/20260823_p5_group3_revoke_admin_user_mgmt_anon_exec.sql`

Applied Production migration record:

`20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`

Exact privilege changes:

```sql
revoke execute on function public.crm_list_users(text) from anon;
revoke execute on function public.crm_upsert_user(text, uuid, text, text, text, text, boolean) from anon;
revoke execute on function public.crm_delete_user(text, uuid) from anon;
```

Exact inverse rollback is preserved in:

`supabase/rollback/20260823_p5_group3_restore_admin_user_mgmt_anon_exec.sql`

Read-only post-check is preserved in:

`supabase/baseline/p5_group3_admin_user_mgmt_anon_exec_check.sql`

## Production post-change verification

The repository post-check confirms all three targets:

- `anon=false`;
- `authenticated=false`;
- `service_role=true`.

Global Production state is now:

- CRM functions: `40`;
- anon EXECUTE: `6` (`9 -> 6`);
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`.

Canonical inventory remains exactly 258 lines. Post-Group-3 fingerprint:

`258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`

The fingerprint delta is expected from the three `FPRIV` transitions only.

## Final merge gate

Before merging PR #23, the final evidence-only head must independently pass Vercel and Cloudflare builds with Group 1/2/3 gates, P3/P4 attack regression, dynamic ADMIN session gating, and Cloudflare P1 parity green.

Merge must use the expected final head SHA. After merge, verify `main`, Vercel Production, Cloudflare Production, Production `40 / 6 / 0 / 40`, RLS `9/9`, latest migration `20260823064535`, and canonical fingerprint `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

## Non-goals

Group 3 does not alter `crm_login_v3`, `crm_public_status`, load/save/logout state RPCs, credential safe-summary/unlock/reveal behavior, any database function body, tables, RLS, policies, Vault, session duration, CSP, WAF, DNS, CRM UI/business behavior, or Groups 4–6 privileges.
