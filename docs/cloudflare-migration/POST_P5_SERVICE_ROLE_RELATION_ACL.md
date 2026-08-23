# Post-P5 service_role direct relation ACL minimization

Last updated: 2026-08-23

## Status

Preparation only. Production currently remains at accepted `main@615d2c966a89d093b62492879b28cd86423ae684` with 40 CRM functions, direct function EXECUTE boundary `PUBLIC/anon/authenticated/service_role = 0/0/0/12`, RLS `9/9`, latest migration `20260823120150 / post_p5_minimize_service_role_rpc_exec`, and canonical fingerprint `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`.

## Goal

Remove direct `service_role` relation access to CRM data while keeping the 12 controlled SECURITY DEFINER function entries intact.

Current direct relation authority:
- 9 CRM tables;
- 7 table privileges per table (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`);
- 63 service-role table grant rows total;
- audit identity sequence `SELECT`, `UPDATE`, `USAGE`.

Proposed direct relation authority after hardening:
- service-role CRM table grants: 0;
- service-role CRM sequence grants: 0;
- browser-role CRM table/sequence grants: remain 0;
- direct CRM function EXECUTE remains exactly 12 for service_role and 0 for browser roles.

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
- transaction rolled back; Production restored to 63 table grants + sequence privileges.

A second net-zero transaction computed the deterministic expected post-hardening canonical and rolled back:
- inventory lines: `195`;
- SHA-256: `edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`;
- service-role CRM table grant rows: `0`;
- service-role audit-sequence direct privileges: none.

The canonical line count drops from 258 to 195 because the repository-frozen fingerprint includes one `TPRIV` line for each of the 63 current service-role table grants. Sequence ACL is outside that legacy canonical inventory, so it is checked separately by the post-check.

## Exact package

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

## Hard gate

No Production relation ACL change is allowed until the exact preparation head passes Vercel and Cloudflare previews, predecessor security gates remain green, and a fresh Production freeze confirms:
- functions `40`, service-role function EXECUTE `12`, browser/PUBLIC function EXECUTE `0`;
- service-role CRM table grant rows `63` across 9 tables;
- service-role audit sequence SELECT/UPDATE/USAGE all present;
- RLS `9/9`;
- latest migration `20260823120150`;
- canonical `258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691`.

Expected post-change state:
- function boundary unchanged at `0 / 0 / 0 / 12`;
- service-role CRM table grants `63 -> 0`;
- service-role CRM sequence privileges `3 -> 0`;
- RLS `9/9`;
- expected canonical `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.
