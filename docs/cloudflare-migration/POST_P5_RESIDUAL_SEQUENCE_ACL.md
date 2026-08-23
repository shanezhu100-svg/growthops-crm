# Post-P5 Residual Sequence ACL Hardening

Last updated: 2026-08-23

## Status

Preparation only. P5 Groups 1–6 are complete and merged at accepted `main@e132c5b9919be6d484f222e5a9dff3eba1944976`. This follow-up does not reopen P5 or change Production at this checkpoint.

## Finding

A post-P5 full ACL audit confirmed the intended CRM function/table boundary:

- CRM functions: `40`;
- `PUBLIC EXECUTE`: `0`;
- `anon EXECUTE`: `0`;
- `authenticated EXECUTE`: `0`;
- `service_role EXECUTE`: `40`;
- browser-role direct CRM table grants: `0`;
- RLS: `9/9`;
- canonical P5 fingerprint: `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`.

The same audit found one residual CRM sequence ACL outside the canonical 258-line inventory:

`public.crm_server_audit_logs_id_seq`

Current pre-hardening sequence privileges:

- `PUBLIC`: no sequence privilege;
- `anon`: `SELECT + UPDATE + USAGE`;
- `authenticated`: `SELECT + UPDATE + USAGE`;
- `service_role`: `SELECT + UPDATE + USAGE`;
- owner: `postgres`.

The sequence is the `IDENTITY ALWAYS` backing sequence for `public.crm_server_audit_logs.id`.

## Risk and scope

Browser roles still have no direct grant on `crm_server_audit_logs`, and RLS is enabled, so this residual sequence ACL does not by itself expose audit rows or permit direct audit-table inserts through the current CRM access model. It is nevertheless unnecessary authority and sits outside the canonical function/table/RLS fingerprint.

The follow-up therefore removes only browser-role privileges from this one sequence and preserves the server path unchanged.

## Dependency proof

All CRM functions whose definitions reference `crm_server_audit_logs` are `SECURITY DEFINER`, owned by `postgres`. They therefore do not rely on `anon` or `authenticated` sequence privileges. `service_role` retains full sequence privileges.

The current `postgres` default ACL in schema `public` already grants new sequences only to `postgres` and `service_role`. A broader historical default ACL exists for objects created by `supabase_admin`, but this follow-up deliberately does **not** alter global `supabase_admin` defaults because doing so could affect unrelated Supabase objects outside the CRM scope.

## Prepared forward migration

`supabase/migrations/20260823_revoke_browser_audit_sequence_acl.sql`

Exact intended changes:

```sql
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from anon;
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from authenticated;
```

## Exact rollback

`supabase/rollback/20260823_restore_browser_audit_sequence_acl.sql`

The rollback restores exactly the two pre-hardening role ACLs and nothing else.

## Read-only post-check

`supabase/baseline/post_p5_audit_sequence_acl_check.sql`

Expected post-change result:

- `PUBLIC SELECT/UPDATE/USAGE = false`;
- `anon SELECT/UPDATE/USAGE = false`;
- `authenticated SELECT/UPDATE/USAGE = false`;
- `service_role SELECT/UPDATE/USAGE = true`;
- owner remains `postgres`;
- total CRM sequences remains `1`.

## Canonical fingerprint note

The existing P5 canonical inventory covers `COL / CON / IDX / TRG / FUNC / FPRIV / TPRIV / RLS / POL`; it does not include sequence ACL rows. Therefore this hardening is expected to leave the canonical `258 / 40aa990f...` fingerprint unchanged. This follow-up adds an explicit sequence ACL regression gate instead of retroactively changing the accepted P5 fingerprint algorithm.

## Hard gate

Do not apply the migration until the exact branch head is green on both Vercel and Cloudflare, all P5/P3/P4 gates remain green, and a fresh Production preflight still confirms the exact residual sequence ACL plus the accepted P5 `40 / 0 / 0 / 40`, RLS `9/9`, migration `20260823101656`, and canonical fingerprint `40aa990f...`.

After any apply, verify the sequence ACL directly, re-check the P5 canonical state is unchanged, and retain the exact inverse rollback.
