# P5 Group 2 Candidate — Retire Legacy Credential Status RPC

Last updated: 2026-08-22

## Status

Preparation only. This branch does **not** change Production database privileges and must not be merged ahead of P5 Group 1 acceptance.

## Candidate scope

The only candidate in this preparation stage is:

- `crm_client_credential_status(text, text)`

No forward `REVOKE` migration is included yet. No rollback migration is included yet. No database DDL/DML/grant change is performed by this branch.

## Why this RPC is a strong next candidate

The live Production function currently has explicit `anon` and `service_role` EXECUTE privileges and no `authenticated` EXECUTE privilege. It is a `SECURITY DEFINER` function and requires a valid CRM session plus `ADMIN` or `OPS` role internally.

However, the shipped browser runtime no longer depends on it:

- the final credential UI uses `crm_client_account_safe_summary` for the controlled non-secret account/credential summary;
- `credential_ui_v6_finalize.py` treats `crm_client_credential_status` as forbidden legacy runtime text and aborts the build if it survives;
- `test_credential_ui_v6_output.py` likewise requires the legacy RPC to be absent from the final runtime;
- neither the Vercel nor the Cloudflare `/api/crm` BFF allowlist contains `crm_client_credential_status`.

The older credential-status finalizer files remain build-time compatibility scaffolding only. The v6 finalizer removes their cache/request/rendering path before the shipped artifacts are produced.

## Required predecessor gate

Do not advance Group 2 until P5 Group 1 has completed its human acceptance and merge sequence:

1. authenticated CRM login/state load succeeds on the Cloudflare Group 1 Preview;
2. authenticated CRM login/state load succeeds on the Vercel rollback Preview;
3. an ADMIN enters their own password and confirms credential unlock succeeds without sharing the password;
4. an already-unlocked ADMIN confirms one scalar v5 reveal succeeds without sharing the revealed value;
5. Group 1 exact-head remains green on both hosting platforms and is merged by the expected SHA;
6. post-merge Production smoke/fingerprint checks pass.

## Group 2 preflight gate

Before creating a revoke migration, require all of the following against the then-current branch/Production state:

- `crm_client_credential_status` remains absent from final browser runtime output;
- both BFF allowlists continue to reject `crm_client_credential_status`;
- `crm_client_account_safe_summary` remains present in the final credential runtime and BFF allowlists;
- Production shows `anon=true`, `authenticated=false`, `service_role=true` for `crm_client_credential_status` before the change;
- no current server integration outside the two BFFs depends on an `anon` call to this RPC;
- the P3/P4 security inventory and Group 1 post-change fingerprint are still stable before the new privilege change.

## Intended later change

If the preflight gate passes, a later dedicated migration may revoke only:

`EXECUTE ON FUNCTION public.crm_client_credential_status(text, text) FROM anon`

That statement is intentionally documentation only at this stage. The actual migration must be created through the project’s normal Supabase migration workflow, with an exact inverse rollback and a read-only post-change privilege check.

Expected privilege shape after that later change:

- `anon=false`
- `authenticated=false`
- `service_role=true`
- total anon-executable CRM RPC count decreases from 10 to 9, assuming no unrelated privilege changes occur first.

## Non-goals

This candidate branch does not alter:

- `crm_login_v3` or `crm_public_status`;
- session/state RPCs;
- user-management RPCs;
- `crm_client_account_safe_summary`;
- credential unlock or scalar reveal behavior;
- tables, RLS, policies, Vault, session duration, CSP, WAF, Access, DNS, UI, or CRM business behavior.

Keeping this as a one-RPC group makes rollback and attribution deterministic and avoids mixing a proven dead runtime path with still-live session or public-boundary RPCs.
