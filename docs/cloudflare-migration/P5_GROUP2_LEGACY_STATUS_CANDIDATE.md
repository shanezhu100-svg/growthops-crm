# P5 Group 2 Candidate — Retire Legacy Credential Status RPC

Last updated: 2026-08-23

## Status

Group 1 predecessor gate is complete and merged to `main` at `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`.

This Group 2 branch is now rebased by reconstruction onto that accepted `main`. It remains preparation-only at this checkpoint: no Group 2 Production privilege change, forward revoke migration, rollback migration, or database DDL/DML is included yet.

## Candidate scope

The only Group 2 candidate is:

- `crm_client_credential_status(text, text)`

## Why this RPC is a strong next candidate

The shipped browser runtime no longer depends on it:

- the final credential UI uses `crm_client_account_safe_summary` for the controlled non-secret account/credential summary;
- `credential_ui_v6_finalize.py` explicitly forbids `crm_client_credential_status` from surviving into shipped runtime;
- `test_credential_ui_v6_output.py` likewise requires the legacy RPC to be absent from final runtime output;
- neither the Vercel nor Cloudflare `/api/crm` BFF allowlist contains `crm_client_credential_status`.

The older credential-status finalizer files remain build-time compatibility scaffolding only. The v6 finalizer strips the legacy request/cache/rendering path before shipped artifacts are produced.

## Accepted predecessor baseline

Group 1 is complete with:

- merged `main`: `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`;
- Production CRM functions: `40`;
- Production anon EXECUTE: `10`;
- Production authenticated EXECUTE: `0`;
- Production service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest accepted Production migration: `20260823045642 / credential_unlock_reauth_bridge`;
- canonical Production security fingerprint: `258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e`.

## Group 2 preflight gate

Before creating or applying a revoke migration, require all of the following against the current branch and live Production state:

- `crm_client_credential_status` remains absent from both BFF allowlists;
- `crm_client_credential_status` remains forbidden from final browser runtime output;
- `crm_client_account_safe_summary` remains present in both BFF allowlists and final credential runtime;
- Production shows `anon=true`, `authenticated=false`, `service_role=true` for `crm_client_credential_status` before Group 2;
- no current shipped browser path depends on this legacy RPC;
- P3/P4 hard security gates remain PASS;
- Group 1 privilege counts and the accepted 258-line fingerprint remain stable before the Group 2 privilege change.

## Intended Group 2 change

If the preflight gate passes, Group 2 may revoke only:

`EXECUTE ON FUNCTION public.crm_client_credential_status(text, text) FROM anon`

The actual forward migration must be created through the project’s normal Supabase migration workflow, paired with an exact inverse rollback and a read-only post-change privilege check.

Expected privilege shape after Group 2:

- `crm_client_credential_status`: `anon=false`, `authenticated=false`, `service_role=true`;
- total anon-executable CRM RPC count: `10 -> 9`;
- total service_role-executable CRM RPC count remains `40`.

## Non-goals

Group 2 does not alter:

- `crm_login_v3` or `crm_public_status`;
- session/state RPCs;
- user-management RPCs;
- `crm_client_account_safe_summary`;
- credential unlock or scalar reveal behavior;
- tables, RLS, policies, Vault, Session duration, CSP, WAF, Access, DNS, UI, or CRM business behavior.

Keeping this as a one-RPC group preserves deterministic rollback and attribution.
