# P5 Incremental RPC Revocation — Group 1

Last updated: 2026-08-22

## Scope

P5 removes the transitional Supabase `anon` EXECUTE surface only after both Cloudflare and Vercel BFFs have been proven with backend-only `sb_secret_...` server identity.

Group 1 is intentionally limited to the two credential-sensitive RPCs:

- `crm_unlock_credentials_v1(text, text)`
- `crm_reveal_client_secret_value_v5(text, text, text, text, text, text)`

The Production permission migration changes only EXECUTE grants for those two functions. It does **not** change function definitions, CRM tables, RLS, policies, Session/Vault design, CSP, WAF, Access, DNS, or any later-group RPC grant.

During post-revoke human acceptance, a browser-only credential-field liveness defect was discovered: the safe-summary/card renderer could replace the DOM containing the per-field eye control while ADMIN unlock or scalar reveal was in flight. Group 1 therefore also contains a narrowly scoped runtime repair and regression gate for that existing credential UI path. The repair does not change database permissions or reveal transport: final browser reveal remains `crm_reveal_client_secret_value_v5` only.

## Preflight state

Production read-only ACL inspection before Group 1 showed both functions had explicit ACL entries for `anon` and `service_role`, with no `PUBLIC` inheritance:

- `crm_unlock_credentials_v1`: `anon=true`, `authenticated=false`, `service_role=true`
- `crm_reveal_client_secret_value_v5`: `anon=true`, `authenticated=false`, `service_role=true`

The complete pre-P5 CRM function surface contained 12 anon-executable RPCs. Group 1 reduced this to exactly 10 while leaving `service_role` execution on all 40 CRM functions intact.

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

Expected and observed Production result after Group 1:

- `sensitive_anon_exec = 0`
- `sensitive_authenticated_exec = 0`
- `sensitive_service_exec = 2`
- `total_anon_crm_exec = 10`
- `total_service_crm_exec = 40`
- `sensitive_anon_names = null`
- `sensitive_missing_service_names = null`

The existing P3/P4 security inventory changed only in the intentional gate `sensitive_anon_surface_pre_p5`, from `PENDING_P5` to `PASS_P5_COMPLETE`. All other hard gates remained PASS.

Frozen post-Group-1 Production security fingerprint:

`258 / 4d6ab3cbfabc5f374fb97af6ca7ac5aaebc6632e1984da0b20182ff47f84d173`

## Automated repository gates

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

`test_credential_eye_self_heal_output.py` additionally verifies the browser-only repair discovered during human acceptance:

- a stale reveal-installed marker is not trusted unless the real per-field eye button exists;
- if ADMIN unlock causes a card DOM replacement, the controller reacquires only the uniquely matching live account row;
- if scalar v5 reveal completes and the card is replaced again, the already-returned value may be rehydrated only for the same client + platform + account and only inside the original 10-second display window;
- the short-lived value is kept in memory only and is cleared on hide/background/navigation;
- no legacy broad reveal, v3 reveal, v4 reveal, `localStorage`, or `sessionStorage` credential path is restored.

Final shipped runtime audit confirms one canonical per-field eye installer/click handler and one `crm_reveal_client_secret_value_v5` browser call site; legacy reveal-button entry points are absent.

## Production execution record

1. Exact branch Preview gates passed before Production permission change.
2. Group 1 migration applied to Production as remote migration `20260822151709 / p5_revoke_sensitive_anon_exec_group1`.
3. Immediate privilege check passed: sensitive anon=0, authenticated=0, service_role=2; total anon CRM EXECUTE=10; service_role CRM EXECUTE=40.
4. Cloudflare and Vercel server-identity smoke remained normal after revoke; no rollback trigger observed.
5. Full P3/P4 read-only inventory remained PASS and the new deterministic Production fingerprint was frozen as `258 / 4d6ab3cbfabc5f374fb97af6ca7ac5aaebc6632e1984da0b20182ff47f84d173`.

## Human acceptance status

- Cloudflare Group 1 Preview login + refresh + real CRM state load: **PASS (user-attested)**.
- Vercel Group 1 Preview login + refresh + real CRM state load: **PASS (user-attested)**.
- ADMIN password unlock after revoke: **PASS (user-attested; unlock succeeded)**.
- Backend audit observed scalar reveal activity immediately after the successful unlock, confirming the server-side unlock/v5 path was reached; however the human visual gate is **still pending** until the ADMIN confirms a credential becomes visible briefly and is automatically hidden again.

The human visual reveal gate was delayed by the credential-card DOM liveness defect described above. The current exact branch head contains the repair and dedicated regression gate. Do not mark Group 1 fully accepted or merge until the ADMIN visually confirms the final behavior without sharing the revealed value.

## Final merge sequence

1. Keep `main` fixed at the expected predecessor while acceptance is open.
2. Require the exact final Group 1 branch head green on Vercel and Cloudflare.
3. ADMIN performs one final visual scalar reveal test on the current Cloudflare Group 1 branch Preview: value appears briefly and returns to masked state after about 10 seconds. Do not send the value to ChatGPT.
4. Record that final human gate as PASS.
5. Re-check PR/head/main, exact-head deployments, Production privilege snapshot, and frozen Production fingerprint.
6. Mark PR Ready and merge only with the expected head SHA.
7. Verify merged `main`, Production behavior, privileges, and fingerprint before starting Group 2 execution.

## Rollback trigger

Run the permission rollback immediately if either Cloudflare or Vercel cannot execute either sensitive RPC through the server-only identity while `service_role` privilege is expected to remain present. A browser-only rendering defect is **not** a permission rollback trigger when server identity and the two sensitive RPCs are demonstrably functioning; fix and re-validate the UI separately. After any permission rollback, verify anon execution is restored only for the two Group 1 functions and re-run the previous P3/P4 fingerprint/security checks.

## Later P5 groups

Do not combine later revokes into Group 1. Groups 2–6 remain separate preparation PRs and must not be applied or merged ahead of their predecessors. `crm_login_v3` and `crm_public_status` remain a separate final public-boundary group.
