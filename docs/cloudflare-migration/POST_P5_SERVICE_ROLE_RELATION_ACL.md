# Post-P5 service_role direct relation ACL minimization

Last updated: 2026-08-23

## Status

Production hardening is applied and verified. Accepted predecessor was `main@615d2c966a89d093b62492879b28cd86423ae684` with 40 CRM functions, function EXECUTE boundary `PUBLIC/anon/authenticated/service_role = 0/0/0/12`, RLS `9/9`, latest migration `20260823120150 / post_p5_minimize_service_role_rpc_exec`, and canonical fingerprint `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`.

## Goal and exact scope

Remove direct `service_role` relation access to CRM data while keeping the 12 controlled SECURITY DEFINER function entries intact.

Pre-change direct relation authority:
- 9 CRM tables;
- 7 table privileges per table (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`);
- 63 service-role table grant rows total;
- audit identity sequence `SELECT`, `UPDATE`, `USAGE`.

Post-change direct relation authority:
- service-role CRM table grants: 0;
- service-role CRM sequence grants: 0;
- browser-role CRM table/sequence grants: remain 0;
- direct CRM function EXECUTE remains exactly 12 for service_role and 0 for PUBLIC/anon/authenticated.

## Dependency proof

All 12 preserved entry/operations functions are postgres-owned SECURITY DEFINER functions with explicit `search_path`. All 9 CRM tables are postgres-owned and RLS-enabled. Both BFFs call only `/rest/v1/rpc/<allowlisted RPC>` and do not use direct CRM table endpoints.

A live net-zero transaction temporarily revoked all 63 service-role CRM table grants plus the three audit-sequence privileges, switched to `service_role`, exercised the preserved entry set, verified direct table/sequence denial, and rolled back.

Rehearsal result:
- RPC permission-denied tests: 0;
- `crm_public_status`, `crm_login_v3`, and `crm_logout`: entered successfully;
- session-bound RPCs: reached expected `INVALID_SESSION` (`P0001`), not ACL denial;
- `crm_bootstrap_admin`: reached expected `ALREADY_INITIALIZED` (`P0001`), not ACL denial;
- direct `crm_users` read: `42501 permission denied`;
- direct Vault-table read: `42501 permission denied`;
- direct audit sequence `nextval`: `42501 permission denied`;
- transaction rolled back; Production restored to 63 table grants + sequence privileges before the real apply.

A second net-zero transaction computed the deterministic expected post-hardening canonical and rolled back:
- inventory lines: `195`;
- SHA-256: `edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`;
- service-role CRM table grant rows: `0`;
- service-role audit-sequence direct privileges: none.

The canonical line count drops from 258 to 195 because the frozen fingerprint includes one `TPRIV` line for each of the 63 prior service-role table grants. Sequence ACL is outside that legacy canonical inventory and is checked separately.

## Package

Forward migration:
`supabase/migrations/20260823_post_p5_revoke_service_role_relation_acl.sql`

Rollback:
`supabase/rollback/20260823_post_p5_restore_service_role_relation_acl.sql`

Read-only preflight:
`supabase/baseline/post_p5_service_role_relation_acl_preflight.sql`

Read-only post-check:
`supabase/baseline/post_p5_service_role_relation_acl_check.sql`

Static build gate:
`test_post_p5_service_role_relation_acl.py`

## Pre-apply evidence

Preparation head:
`703e11a8cfdd1c7d276b919607213ad7ace2b2f1`

Vercel:
- deployment `dpl_JQHLuiZMEvY2SAS311n5MeEv32mB`;
- READY;
- relation ACL gate PASS;
- predecessor/P3P4 gates PASS.

Cloudflare:
- deployment `353009e3-24f4-4742-8ddf-c8b3f9a5246b`;
- exact URL `https://353009e3.growthops-crm.pages.dev/`;
- success;
- relation ACL gate PASS;
- P1 output parity PASS.

Fresh Production freeze immediately before apply confirmed:
- functions 40;
- function EXECUTE `0 / 0 / 0 / 12`;
- service-role CRM table grant rows 63 across 9 tables;
- service-role audit sequence SELECT/UPDATE/USAGE all present;
- browser relation grants absent;
- RLS `9/9`;
- latest migration `20260823120150 / post_p5_minimize_service_role_rpc_exec`;
- canonical `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`.

## Production result

Applied migration:

`20260823123328 / post_p5_revoke_service_role_relation_acl`

Verified state:
- function boundary unchanged at `0 / 0 / 0 / 12`;
- service-role CRM table grants `63 -> 0`;
- service-role CRM sequence privileges `3 -> 0`;
- browser CRM table grants: 0;
- browser audit-sequence privileges: 0;
- RLS `9/9`;
- canonical `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.

Post-apply transaction smoke test:
- preserved RPC permission-denied count: 0;
- public/login/logout entries enter normally;
- session-bound RPCs reach expected `INVALID_SESSION`;
- bootstrap reaches expected `ALREADY_INITIALIZED`;
- direct users-table read, Vault-table read, and audit-sequence `nextval` each return `42501 permission denied`.

## Final merge gate

The final evidence-only head must pass Vercel and Cloudflare with this relation ACL gate, predecessor/P3P4 gates, and Cloudflare P1 parity green. Immediately before merge, re-confirm Production at `40 funcs / 0 PUBLIC / 0 anon / 0 authenticated / 12 service_role`, 0 service-role CRM table grants, 0 service-role audit-sequence direct privileges, RLS `9/9`, migration `20260823123328`, and canonical `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.
