# Post-P5 CRM ACL Event Guard

## Purpose

Prevent future CRM migrations from silently reopening the least-privilege boundary that is already enforced in Production.

Accepted predecessor:
- `main@cb466292535508325fadb7ebe0ba1626755f1e3c`
- migration `20260823131002 / post_p5_login_trusted_source_bucket`
- CRM functions `40`
- function EXECUTE `PUBLIC/anon/authenticated/service_role = 0/0/0/12`
- direct CRM relation/sequence ACL for browser/service roles = `0`
- RLS `9/9`
- canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`

Production change: **not applied** in this preparation commit.

## Risk found

A transaction probe showed that a newly-created `public.crm_*` function inherits PostgreSQL's built-in PUBLIC EXECUTE and the project's service-role defaults. A new CRM table/identity sequence also inherits service-role direct relation privileges. Therefore a future migration that forgets explicit revokes could undo P5/post-P5 hardening immediately.

Changing global `ALTER DEFAULT PRIVILEGES` for `postgres` would be too broad because PostgreSQL function PUBLIC EXECUTE is a global default and the same owner may create objects outside CRM scope. The guard therefore uses a prefix-specific `ddl_command_end` event trigger instead.

## Guard behavior

Infrastructure function: `public.growthops_crm_acl_guard_ddl()`.

It is SECURITY DEFINER, owned by `postgres`, uses fixed `search_path=pg_catalog`, and is not itself a CRM RPC. Its EXECUTE privilege is revoked from PUBLIC, anon, authenticated and service_role.

For `public.crm_*` DDL:

- functions: revoke PUBLIC/anon/authenticated EXECUTE after CREATE or ALTER;
- service_role: preserve/grant EXECUTE only for the exact 12 approved signatures (11 BFF RPCs plus `crm_bootstrap_admin`), revoke it for every other CRM function;
- procedures: revoke EXECUTE from PUBLIC/anon/authenticated/service_role;
- tables, partitioned tables, views, materialized views and foreign tables: revoke all direct privileges from PUBLIC/anon/authenticated/service_role;
- sequences, including identity sequences: revoke all direct privileges from PUBLIC/anon/authenticated/service_role;
- CREATE and ALTER/rename paths are both covered so a non-CRM object cannot bypass the guard by later being renamed to `crm_*`.

The migration does **not** alter global default privileges and does not modify any BFF/runtime file.

## Exact service-role allowlist

1. `crm_bootstrap_admin(p_setup_code text, p_name text, p_username text, p_password text)`
2. `crm_client_account_safe_summary(p_token text, p_client_id text)`
3. `crm_delete_user(p_token text, p_user_id uuid)`
4. `crm_list_users(p_token text)`
5. `crm_load_state_v3(p_token text)`
6. `crm_login_v3(p_username text, p_password text)`
7. `crm_logout(p_token text)`
8. `crm_public_status()`
9. `crm_reveal_client_secret_value_v5(p_token text, p_unlock_token text, p_client_id text, p_platform text, p_account_id text, p_field text)`
10. `crm_save_state(p_token text, p_state jsonb, p_expected_revision bigint)`
11. `crm_unlock_credentials_v1(p_token text, p_password text)`
12. `crm_upsert_user(p_token text, p_user_id uuid, p_name text, p_username text, p_password text, p_role text, p_enabled boolean)`

Any future server RPC must intentionally update this allowlist and its tests; otherwise it remains fail-closed.

## Production rehearsals

All rehearsals were performed inside explicit transactions and ended in `ROLLBACK`.

### Default-grant probe

Before the guard, newly-created CRM objects showed:
- function: PUBLIC/anon/authenticated/service_role EXECUTE = true;
- table: service_role direct read/write = true;
- identity/standalone sequence: service_role SELECT/UPDATE/USAGE = true.

### Guard probe

With the candidate guard installed transactionally:
- new CRM function: PUBLIC/anon/authenticated/service_role EXECUTE = false;
- explicit service-role opt-in after creation = true;
- allowlisted `crm_public_status()` survived `CREATE OR REPLACE` with browser=false/service_role=true;
- new CRM table: browser/service-role direct privileges = false;
- identity and standalone sequences: service-role SELECT/UPDATE/USAGE = false;
- guard infrastructure function: PUBLIC/anon/authenticated/service_role EXECUTE = false;
- existing approved service-role function count stayed exactly `12`;
- canonical stayed exactly `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.

### Rename/procedure bypass probe

A non-CRM function renamed to `crm_*`, a non-CRM table renamed to `crm_*`, and a newly-created `crm_*` procedure all ended with browser/service_role access = false. The transaction was rolled back.

After the rehearsals, Production was checked for residue: no guard event trigger, no guard function and no probe object remained.

## Rollback

Rollback drops only the event trigger and infrastructure guard function. It intentionally does not grant anything back to CRM objects that may have been created while the guard was active; automatic privilege broadening during rollback would be unsafe.

## Acceptance gates

Before apply:
1. exact preparation head passes Vercel and Cloudflare builds;
2. all predecessor P3/P4/session/P5/post-P5 gates remain green;
3. Cloudflare P1 parity remains green;
4. fresh Production preflight confirms no guard is installed and the boundary remains `40 / 0/0/0/12 / relation ACL 0 / RLS 9/9 / canonical 195+a69eba75`;
5. PR head/base and mergeability are unchanged.

After apply:
1. event trigger exists and is enabled;
2. guard function is postgres-owned SECURITY DEFINER with `search_path=pg_catalog` and no external EXECUTE;
3. existing CRM boundary remains `0/0/0/12` and direct relation ACL remains `0`;
4. canonical remains exactly `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`;
5. a transaction probe verifies new/renamed CRM objects fail closed;
6. final evidence-only head passes Vercel and Cloudflare before Ready/merge.
