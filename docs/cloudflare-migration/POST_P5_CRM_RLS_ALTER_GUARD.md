# Post-P5 CRM ALTER-table RLS Guard

## Purpose

Close the remaining RLS drift path when a CRM table enters `public` through `ALTER TABLE` (SET SCHEMA / rename-to-`crm_*`).

Accepted predecessor:
- `main@c22750d639d1b08a6e6f387f889d6de62b5c2ca7`;
- migration `20260823135410 / post_p5_crm_acl_event_guard`;
- CRM function EXECUTE `PUBLIC/anon/authenticated/service_role = 0/0/0/12`;
- direct CRM relation/sequence ACL = `0`;
- CRM tables with RLS = `9/9`;
- canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.

Production change: **applied + verified**.

## Risk found

The existing `ensure_rls` event trigger listens only to `CREATE TABLE`, `CREATE TABLE AS`, and `SELECT INTO`. A transaction probe showed that a table created outside `public` can later be moved into `public` with a `crm_*` name and remain `relrowsecurity=false`.

The already-installed CRM ACL guard correctly revoked browser/service-role direct access on that moved table, so this was not an immediate browser exposure. It did, however, break the long-term `RLS=on for every CRM table` invariant.

## Guard behavior

Infrastructure function: `public.growthops_crm_rls_guard_ddl()`.

- owner `postgres`;
- SECURITY DEFINER;
- fixed `search_path=pg_catalog`;
- external EXECUTE revoked from PUBLIC/anon/authenticated/service_role;
- event trigger listens only to `ALTER TABLE`;
- only `public.crm_*` tables / partitioned tables are considered;
- when `relrowsecurity=false`, it issues `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`;
- nested invocation is bounded because the second invocation sees RLS already enabled and performs no further ALTER.

The existing create-time `ensure_rls` guard and `growthops_crm_acl_guard_ddl` ACL guard remain unchanged.

## Pre-apply rehearsal

The candidate guard was installed inside an explicit transaction and rolled back. Verified:
- external-schema `crm_*` table moved into public -> RLS true;
- public non-CRM table renamed to `crm_*` -> RLS true;
- normal public `crm_*` create -> RLS true through existing `ensure_rls`;
- service-role direct access remained false through the ACL guard;
- guard owner was postgres and service-role EXECUTE was false.

Residue after rollback: no RLS guard function/event and no probe relation remained; existing ACL guard stayed installed.

## Preparation evidence

Preparation initially failed only because the static test incorrectly rejected an `ensure_rls` mention in a migration comment. SQL/rollback were unchanged; the gate was corrected to forbid replacement/drop of the existing create-time guard rather than textual mention.

Verified preparation head:
`663f57885d23a0c2b892dc47dea4fc2b76bb0955`

Vercel:
- deployment `dpl_F9TKf9b9yfU1qQ9WBRZVvBgg3Zri`;
- READY;
- exact commit `663f5788...`;
- `POST_P5_CRM_RLS_ALTER_GUARD_OK` PASS with `production-change=none`;
- predecessor security gates PASS.

Cloudflare:
- deployment `668940c2-9d1d-4e21-b3e7-b826bfbbd6d3`;
- exact URL `https://668940c2.growthops-crm.pages.dev/`;
- success;
- exact commit `663f5788...`;
- RLS ALTER guard gate PASS;
- `CLOUDFLARE_P1_OUTPUT_PARITY_OK` PASS.

Fresh pre-apply Production freeze confirmed zero drift: functions `40`, anon/auth/service `0/0/12`, CRM tables `9`, RLS `9/9`, direct table grants `0`, existing create-time RLS + ACL guards present, ALTER-table RLS guard absent, migration `20260823135410`, canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`. PR #34 remained mergeable with exact preparation head.

## Production result

Applied migration:
`20260823143620 / post_p5_crm_rls_alter_guard`

Immediate post-check verified:
- CRM functions `40`;
- anon/authenticated/service-role function EXECUTE `0/0/12`;
- CRM tables `9`, RLS `9/9`;
- direct table grants `0`;
- new event trigger enabled with exact tag `ALTER TABLE`;
- event/function owner `postgres`;
- guard is SECURITY DEFINER with `search_path=pg_catalog`;
- anon/authenticated/service_role EXECUTE on guard all false;
- existing `ensure_rls` and ACL guard remain present;
- canonical remains exactly `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.

## Installed-guard transaction probe

After apply, the installed Production guard was exercised inside a transaction and rolled back:
- external-schema CRM table moved into public -> RLS true;
- public table renamed to `crm_*` -> RLS true;
- anon/service direct SELECT on both remained false through the ACL guard.

A residue check confirmed no probe relation remained and the installed guard remained present.

## Rollback

Rollback drops only `growthops_crm_rls_guard_ddl` event trigger and infrastructure function. It does not alter `ensure_rls`, `growthops_crm_acl_guard_ddl`, table ACLs, or existing RLS state.

## Final acceptance

Before merge:
1. final evidence-only head must differ from verified preparation only in this document and static gate status;
2. final exact head must pass Vercel and Cloudflare;
3. predecessor gates and Cloudflare P1 parity must remain green;
4. final Production freeze must confirm both RLS guards + ACL guard present, boundary `40 / 0/0/12`, RLS `9/9`, direct relation ACL `0`, migration `20260823143620`, canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`;
5. merge only with the exact verified head SHA.
