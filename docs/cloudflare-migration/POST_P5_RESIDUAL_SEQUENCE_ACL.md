# Post-P5 Residual Sequence ACL Hardening

Last updated: 2026-08-23

## Status

Production hardening is applied and verified. P5 Groups 1–6 remain complete at accepted `main@e132c5b9919be6d484f222e5a9dff3eba1944976`; this follow-up changes only the residual browser-role ACL on one CRM audit sequence.

## Accepted P5 baseline

- CRM functions: `40`;
- `PUBLIC EXECUTE`: `0`;
- `anon EXECUTE`: `0`;
- `authenticated EXECUTE`: `0`;
- `service_role EXECUTE`: `40`;
- browser-role direct CRM table grants: `0`;
- RLS: `9/9`;
- pre-follow-up migration: `20260823101656 / p5_group6_revoke_public_boundary_anon_exec`;
- canonical P5 fingerprint: `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`.

## Finding

The full ACL audit found exactly one CRM sequence:

`public.crm_server_audit_logs_id_seq`

It is the `IDENTITY ALWAYS` backing sequence for `public.crm_server_audit_logs.id`, owner `postgres`. Before this hardening:

- `PUBLIC`: no sequence privilege;
- `anon`: `SELECT + UPDATE + USAGE`;
- `authenticated`: `SELECT + UPDATE + USAGE`;
- `service_role`: `SELECT + UPDATE + USAGE`.

Browser roles had no direct audit-table grant and RLS was enabled, so the residual sequence ACL was not an audit-row disclosure path. It was nevertheless unnecessary authority outside the P5 canonical inventory.

## Dependency proof

All CRM functions whose definitions reference `crm_server_audit_logs` are `SECURITY DEFINER`, owned by `postgres`; they do not rely on `anon` or `authenticated` sequence privileges. `service_role` keeps full sequence authority.

The current `postgres` default ACL in schema `public` already gives new sequences only to `postgres` and `service_role`. A broader historical default ACL exists for `supabase_admin`; this follow-up does **not** alter global `supabase_admin` defaults because doing so could affect unrelated Supabase objects.

## Exact migration and rollback

Forward migration file:

`supabase/migrations/20260823_revoke_browser_audit_sequence_acl.sql`

```sql
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from anon;
revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from authenticated;
```

Exact inverse rollback:

`supabase/rollback/20260823_restore_browser_audit_sequence_acl.sql`

Read-only post-check:

`supabase/baseline/post_p5_audit_sequence_acl_check.sql`

## Exact-head pre-apply evidence

Accepted preview head:

`4cc49a68f18f7c896ac3d7021886488c5566901d`

Vercel:

- deployment `dpl_9vVUr8zH5f6jJF8iGLw4AdGFZFEy`;
- state `READY`;
- all P5 Groups 1–6 gates PASS;
- P3/P4 attack regression PASS;
- `POST_P5_AUDIT_SEQUENCE_ACL_OK` PASS.

Cloudflare Pages:

- deployment `575e0cac-a629-4c17-86dd-e593606995fc`;
- exact URL `https://575e0cac.growthops-crm.pages.dev/`;
- status `success`;
- P5 Group6 gates PASS;
- `POST_P5_AUDIT_SEQUENCE_ACL_OK` PASS;
- P1 output parity PASS;
- site deployed successfully.

A final pre-apply Production lock reconfirmed the exact residual ACL, P5 `40 / 0 / 0 / 40`, RLS `9/9`, migration `20260823101656`, and canonical fingerprint `258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`.

## Production execution

Applied migration:

`20260823104232 / post_p5_revoke_browser_audit_sequence_acl`

Verified post-change sequence state:

- owner: `postgres`;
- total CRM sequences: `1`;
- `PUBLIC SELECT/UPDATE/USAGE = false`;
- `anon SELECT/UPDATE/USAGE = false`;
- `authenticated SELECT/UPDATE/USAGE = false`;
- `service_role SELECT/UPDATE/USAGE = true`.

The P5 database boundary is unchanged:

- CRM functions: `40`;
- PUBLIC/anon/authenticated CRM function EXECUTE: `0 / 0 / 0`;
- service_role CRM function EXECUTE: `40`;
- RLS: `9/9`.

## Canonical fingerprint note

The existing P5 canonical inventory covers `COL / CON / IDX / TRG / FUNC / FPRIV / TPRIV / RLS / POL`; it does not include sequence ACL rows. Therefore this hardening correctly leaves the canonical fingerprint unchanged at:

`258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df`

This follow-up adds a dedicated sequence ACL regression gate instead of retroactively changing the accepted P5 fingerprint algorithm.

## Final merge gate

Before merging PR #28, the final evidence-only head must pass Vercel and Cloudflare with `POST_P5_AUDIT_SEQUENCE_ACL_OK`, all P5/P3/P4 gates, and Cloudflare P1 parity green. Immediately before merge, re-check Production sequence ACL, migration `20260823104232`, P5 `40 / 0 / 0 / 40`, RLS `9/9`, and unchanged canonical fingerprint.
