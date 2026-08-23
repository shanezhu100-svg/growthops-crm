# P5 Group 2 — Retire Legacy Credential Status RPC

Last updated: 2026-08-23

## Status

Group 1 predecessor gate is complete and merged to `main` at `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`.

Group 2 preflight is PASS. The branch is reconstructed onto accepted Group 1 `main` and contains the exact forward revoke, inverse rollback, read-only post-check, and repository gate. **The Group 2 Production privilege change has not been applied yet at this checkpoint.**

## Candidate scope

The only Group 2 candidate is:

- `crm_client_credential_status(text, text)`

The shipped browser runtime no longer depends on it:

- final credential UI uses `crm_client_account_safe_summary`;
- `credential_ui_v6_finalize.py` explicitly forbids `crm_client_credential_status` from final runtime output;
- `test_credential_ui_v6_output.py` also forbids it;
- neither the Vercel nor Cloudflare `/api/crm` BFF allowlist contains it.

## Accepted predecessor baseline

Before Group 2 execution, Production is verified as:

- merged `main`: `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`;
- CRM functions: `40`;
- anon EXECUTE: `10`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823045642 / credential_unlock_reauth_bridge`;
- canonical security fingerprint: `258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e`.

Target ACL preflight:

- target count: `1`;
- `anon=true`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`;
- anon EXECUTE is an explicit grant;
- service_role EXECUTE is an explicit grant;
- function remains `SECURITY DEFINER` with existing session and ADMIN/OPS guards.

## Exact Group 2 change

Forward migration:

`supabase/migrations/20260823_p5_group2_revoke_legacy_credential_status_anon_exec.sql`

It contains exactly:

```sql
revoke execute on function public.crm_client_credential_status(text, text) from anon;
```

Emergency rollback:

`supabase/rollback/20260823_p5_group2_restore_legacy_credential_status_anon_exec.sql`

It restores exactly:

```sql
grant execute on function public.crm_client_credential_status(text, text) to anon;
```

Read-only post-change check:

`supabase/baseline/p5_group2_legacy_status_anon_exec_check.sql`

Expected after execution:

- target `anon=false`;
- target `authenticated=false`;
- target `service_role=true`;
- total anon CRM EXECUTE: `10 -> 9`;
- total authenticated CRM EXECUTE: `0`;
- total service_role CRM EXECUTE remains `40`;
- total CRM functions remains `40`.

## Automated gate

`test_p5_group2_legacy_status_revocation.py` requires:

- exactly one forward revoke and no other mutation in the Group 2 migration;
- exactly one inverse rollback grant;
- post-check remains read-only;
- legacy RPC remains absent from both BFFs;
- legacy RPC remains explicitly forbidden by the final credential runtime generator;
- safe-summary replacement remains present in both BFFs and final runtime generation.

Success marker:

`P5_GROUP2_LEGACY_STATUS_REVOCATION_OK: revoke=1-legacy-anon-only; rollback=1-exact-grant; post-check=read-only; expected-anon=9; service-role=40`

## Non-goals

Group 2 does not alter:

- `crm_login_v3` or `crm_public_status`;
- session/state RPCs;
- user-management RPCs;
- `crm_client_account_safe_summary`;
- credential unlock or scalar reveal behavior;
- any function body;
- tables, RLS, policies, Vault, Session duration, CSP, WAF, Access, DNS, UI, or CRM business behavior.

Keeping this as a one-RPC privilege-only group preserves deterministic rollback and attribution.
