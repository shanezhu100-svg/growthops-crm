# P5 Group 2 — Retire Legacy Credential Status RPC

Last updated: 2026-08-23

## Status

Group 1 predecessor gate is complete and merged to `main` at `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`.

Group 2 Production execution is complete. The only privilege change was removal of `anon` EXECUTE from `crm_client_credential_status(text, text)`. The branch now records the forward migration, exact inverse rollback, read-only post-check, exact-head deployment evidence, Production verification, and the new canonical security fingerprint.

## Scope

The only Group 2 RPC is:

- `crm_client_credential_status(text, text)`

The shipped browser runtime does not depend on it:

- final credential UI uses `crm_client_account_safe_summary`;
- `credential_ui_v6_finalize.py` explicitly forbids `crm_client_credential_status` from final runtime output;
- `test_credential_ui_v6_output.py` also forbids it;
- neither the Vercel nor Cloudflare `/api/crm` BFF allowlist contains it.

## Accepted Group 1 baseline

Immediately before Group 2, Production was verified as:

- merged `main`: `e5314a3c4cdf33c5bc2a42bb380fe029321d153e`;
- CRM functions: `40`;
- anon EXECUTE: `10`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823045642 / credential_unlock_reauth_bridge`;
- canonical security fingerprint: `258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e`.

Target ACL preflight was:

- target count: `1`;
- `anon=true`;
- `authenticated=false`;
- `service_role=true`;
- `PUBLIC EXECUTE=false`;
- anon and service_role were explicit grants.

## Exact Group 2 change

Forward migration file:

`supabase/migrations/20260823_p5_group2_revoke_legacy_credential_status_anon_exec.sql`

Exact statement:

```sql
revoke execute on function public.crm_client_credential_status(text, text) from anon;
```

Production migration record:

`20260823062545 / p5_group2_revoke_legacy_credential_status_anon_exec`

Emergency rollback file:

`supabase/rollback/20260823_p5_group2_restore_legacy_credential_status_anon_exec.sql`

Exact inverse:

```sql
grant execute on function public.crm_client_credential_status(text, text) to anon;
```

Read-only post-change check:

`supabase/baseline/p5_group2_legacy_status_anon_exec_check.sql`

## Exact-head evidence before Production execution

Execution-package head: `1dbe523e748c73b3bd62f42b0c6542f04cb165c1`.

Vercel:

- deployment `dpl_A2pkY3p3HksUa4G3W974kMQ54TGy`;
- state `READY`;
- `P5_GROUP2_LEGACY_STATUS_CANDIDATE_OK` PASS;
- `P5_GROUP2_LEGACY_STATUS_REVOCATION_OK` PASS;
- existing Group 1 session/security/reveal and P3/P4 attack-regression gates remain PASS.

Cloudflare Pages:

- deployment `77d5cfdd-ec0b-4305-b555-2ee275e98318`;
- URL `https://77d5cfdd.growthops-crm.pages.dev/`;
- status `success`;
- exact commit `1dbe523e748c73b3bd62f42b0c6542f04cb165c1`;
- `P5_GROUP2_LEGACY_STATUS_CANDIDATE_OK` PASS;
- `P5_GROUP2_LEGACY_STATUS_REVOCATION_OK` PASS;
- `CLOUDFLARE_P3P4_ATTACK_REGRESSION_OK` PASS;
- `CLOUDFLARE_P1_OUTPUT_PARITY_OK` reports Production artifact hashes match.

## Production post-change verification

The repository post-check and an independent ACL/count query both confirm:

- target count: `1`;
- target `anon=false`;
- target `authenticated=false`;
- target `service_role=true`;
- target `PUBLIC EXECUTE=false`;
- CRM functions: `40`;
- anon EXECUTE: `9` (`10 -> 9`);
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS remain `9/9`.

The canonical `p0_schema_security_fingerprint.sql` inventory remains exactly 258 lines. Post-Group-2 fingerprint:

`258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`

This fingerprint change is expected from the single `FPRIV` transition for `crm_client_credential_status`; no function body, table, RLS, policy, Vault, session, UI, or business behavior was changed.

## Automated gates

`test_p5_group2_legacy_status_candidate.py` continues to enforce runtime/BFF independence and now requires the completed Group 2 Production evidence to be recorded.

`test_p5_group2_legacy_status_revocation.py` continues to require:

- exactly one forward revoke and no other mutation in the Group 2 migration;
- exactly one inverse rollback grant;
- post-check remains read-only;
- legacy RPC remains absent from both BFFs and final runtime;
- safe-summary replacement remains preserved.

## Final merge gate

Before merging PR #22, the final evidence-only head must pass Vercel and Cloudflare exact-head builds. Merge must use the expected final head SHA. After merge, verify `main`, hosting deployment state, Production `40 / 9 / 0 / 40`, RLS `9/9`, latest migration `20260823062545`, and canonical fingerprint `258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224`.

## Non-goals

Group 2 does not alter `crm_login_v3`, `crm_public_status`, session/state RPCs, user-management RPCs, `crm_client_account_safe_summary`, credential unlock or scalar reveal behavior, any function body, tables, RLS, policies, Vault, session duration, CSP, WAF, Access, DNS, UI, or CRM business behavior.
