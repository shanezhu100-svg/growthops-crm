# Post-P5 CRM ALTER-table RLS Guard

## Purpose

Close a future RLS drift gap discovered after the fail-closed CRM ACL DDL guard was installed.

Accepted predecessor:
- `main@c22750d639d1b08a6e6f387f889d6de62b5c2ca7`;
- migration `20260823135410 / post_p5_crm_acl_event_guard`;
- CRM function EXECUTE `PUBLIC/anon/authenticated/service_role = 0/0/0/12`;
- direct CRM relation/sequence ACL = `0`;
- CRM tables with RLS = `9/9`;
- canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.

Production change: **not applied** in this preparation commit.

## Risk found

The existing `ensure_rls` event trigger listens only to `CREATE TABLE`, `CREATE TABLE AS`, and `SELECT INTO`. A transaction probe showed that a table created outside `public` can later be moved into `public` with a `crm_*` name and remain `relrowsecurity=false`.

The already-installed CRM ACL guard correctly revoked browser/service-role direct access on that moved table, so this was not an immediate browser exposure. However, it breaks the long-term invariant that every CRM table has RLS enabled and could become relevant to future SECURITY DEFINER or maintenance code.

## Proposed guard

Infrastructure function: `public.growthops_crm_rls_guard_ddl()`.

- SECURITY DEFINER;
- owner `postgres`;
- fixed `search_path=pg_catalog`;
- external EXECUTE revoked from PUBLIC/anon/authenticated/service_role;
- event trigger listens only to `ALTER TABLE`;
- only `public.crm_*` tables / partitioned tables are considered;
- if `relrowsecurity=false`, the guard issues `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`;
- nested invocation is naturally bounded because the second invocation observes `relrowsecurity=true` and performs no further ALTER.

The existing `ensure_rls` create-time guard and `growthops_crm_acl_guard_ddl` ACL guard remain unchanged.

## Deterministic transaction rehearsal

The candidate guard was installed inside an explicit transaction and rolled back. Verified:
- external-schema `crm_*` table moved into public -> RLS true;
- public non-CRM table renamed to `crm_*` -> RLS true;
- normal public `crm_*` table creation -> RLS true through existing `ensure_rls`;
- service-role direct access remained false because the ACL guard still ran;
- guard owner was postgres and service-role EXECUTE was false.

After rollback, Production residue check confirmed no `growthops_crm_rls_guard_ddl` function/event and no probe relation remained. Existing ACL guard stayed installed. Latest migration remained `20260823135410`.

## Migration package

Forward migration:
`supabase/migrations/20260823_post_p5_crm_rls_alter_guard.sql`

Rollback:
`supabase/rollback/20260823_post_p5_crm_rls_alter_guard.sql`

Read-only checks:
- `supabase/baseline/post_p5_crm_rls_alter_guard_preflight.sql`
- `supabase/baseline/post_p5_crm_rls_alter_guard_check.sql`

Static gate:
`test_post_p5_crm_rls_alter_guard.py`

Expected marker:
`POST_P5_CRM_RLS_ALTER_GUARD_OK`

## Expected invariant

Installing this infrastructure guard must not change any current CRM object definition or privilege. Therefore canonical inventory remains exactly:

`195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`

and current boundary remains `40 functions / service-role EXECUTE 12 / direct relation ACL 0 / RLS 9/9`.

## Hard gate

Do not apply Production DDL until the exact preparation head passes Vercel and Cloudflare, predecessor security gates remain green, Cloudflare P1 parity remains green, and a fresh Production freeze confirms zero drift.

After apply, require an installed-guard transaction probe covering SET SCHEMA and rename-to-`crm_*`, zero probe residue, final exact-head dual-platform green, final Production freeze, then expected-head merge.
