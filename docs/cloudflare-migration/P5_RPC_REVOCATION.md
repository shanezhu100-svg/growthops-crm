# P5 Incremental RPC Revocation — Group 1

Last updated: 2026-08-22

## Scope

P5 removes the transitional Supabase `anon` EXECUTE surface only after both Cloudflare and Vercel BFFs have been proven with backend-only `sb_secret_...` server identity.

Group 1 is intentionally limited to the two credential-sensitive RPCs:

- `crm_unlock_credentials_v1(text, text)`
- `crm_reveal_client_secret_value_v5(text, text, text, text, text, text)`

This group does **not** change function definitions, CRM business behavior, Session/Vault design, UI, CSP, WAF, Access, DNS, tables, RLS, policies, or any other RPC grant.

## Preflight state

Production read-only ACL inspection before Group 1 showed both functions had explicit ACL entries for `anon` and `service_role`, with no `PUBLIC` inheritance:

- `crm_unlock_credentials_v1`: `anon=true`, `authenticated=false`, `service_role=true`
- `crm_reveal_client_secret_value_v5`: `anon=true`, `authenticated=false`, `service_role=true`

The complete pre-P5 CRM function surface contains 12 anon-executable RPCs. Group 1 must reduce this to exactly 10 while leaving `service_role` execution on all 40 CRM functions intact.

P0 isolated recovery rehearsal is PASS. P2-B server identity is PASS on both hosting paths. P3/P4 attack-style regression is merged and PASS. These are prerequisites for P5.

## Forward migration

`supabase/migrations/20260822_p5_revoke_sensitive_anon_exec.sql`

The migration contains exactly two permission changes:

```sql
revoke execute on function public.crm_unlock_credentials_v1(text, text) from anon;
revoke execute on function public.crm_reveal_client_secret_value_v5(text, text, text, text, text, text) from anon;
```

No other grant or object is modified.

## Emergency rollback

`supabase/rollback/20260822_p5_restore_sensitive_anon_exec.sql`

Rollback restores exactly the two pre-P5 anon grants and nothing else. Use it only if either server-identity path fails after the revoke.

## Read-only post-change check

`supabase/baseline/p5_sensitive_anon_exec_check.sql`

Expected Production result after Group 1:

- `sensitive_anon_exec = 0`
- `sensitive_authenticated_exec = 0`
- `sensitive_service_exec = 2`
- `total_anon_crm_exec = 10`
- `total_service_crm_exec = 40`
- `sensitive_anon_names = null`
- `sensitive_missing_service_names = null`

The existing P3/P4 security inventory must also change only in the intentional gate `sensitive_anon_surface_pre_p5`, from `PENDING_P5` to `PASS_P5_COMPLETE`. All other hard gates must remain PASS.

## Automated repository gate

`test_p5_sensitive_rpc_revocation.py` verifies:

- the forward migration has exactly two anon revokes;
- the exact two function signatures are targeted;
- no login/public/state/user-management RPC is revoked in Group 1;
- no function definition, table, RLS, Vault, Session, or data statement is present;
- rollback has exactly the two inverse anon grants;
- the read-only check encodes the expected post-P5 privilege shape;
- both Cloudflare and Vercel BFFs still proxy the two sensitive RPC names through `GROWTHOPS_SUPABASE_SECRET_KEY` with no publishable-key fallback.

Success marker:

`P5_SENSITIVE_RPC_REVOCATION_GATE_OK: revoke=2-sensitive-anon-only; rollback=2-exact-grants; server-identity=preserved; runtime=unchanged`

## Production execution order

1. Require the exact final branch head green on Vercel Preview and Cloudflare Preview before touching Production permissions.
2. Confirm the pre-change Production fingerprint remains `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`.
3. Apply only the Group 1 migration to Production.
4. Immediately run `p5_sensitive_anon_exec_check.sql`.
5. Verify Cloudflare and Vercel `/api/crm` still return normal public/session boundary results through server identity.
6. Verify real CRM login/state load on Cloudflare and Vercel rollback paths.
7. With the ADMIN entering their password themselves, verify credential unlock still succeeds. Do not send the password to ChatGPT.
8. With an already-unlocked ADMIN session, verify one v5 scalar credential reveal succeeds without exposing the revealed value to logs, GitHub, backups, or ChatGPT. The user can confirm success without sharing the value.
9. Re-run P3/P4 read-only inventory and the deterministic schema/security fingerprint. The fingerprint is expected to change because function privilege lines intentionally changed; record the new P5 fingerprint as the next frozen baseline.
10. Only after both hosting paths pass may the PR be marked Ready and merged with the expected head SHA.

## Rollback trigger

Run the rollback immediately if, after the forward revoke, either Cloudflare or Vercel cannot execute either sensitive RPC through the server-only identity while `service_role` privilege is expected to remain present. After rollback, verify anon execution is restored only for the two Group 1 functions and re-run the previous P3/P4 fingerprint/security checks.

## Later P5 groups

Do not combine later revokes into Group 1. Candidate groups for separate PRs include user-management/safe-summary RPCs and state/session RPCs. `crm_login_v3` and `crm_public_status` require separate final-boundary design and are not part of this change.
