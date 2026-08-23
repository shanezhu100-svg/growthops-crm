# P5 Incremental RPC Revocation — Group 1

Last updated: 2026-08-23

## Scope

P5 removes the transitional Supabase `anon` EXECUTE surface only after both Cloudflare and Vercel BFFs have been proven with backend-only `sb_secret_...` server identity.

Group 1 is intentionally limited to the two credential-sensitive RPCs:

- `crm_unlock_credentials_v1(text, text)`
- `crm_reveal_client_secret_value_v5(text, text, text, text, text, text)`

The Production permission migration changes only EXECUTE grants for those two functions. It does **not** change CRM tables, RLS, policies, CSP, WAF, Access, DNS, or any later-group RPC grant.

During post-revoke human acceptance, a browser-only credential-field liveness defect was discovered: the safe-summary/card renderer could replace the DOM containing the per-field eye control while ADMIN unlock or scalar reveal was in flight. Group 1 therefore also contains a narrowly scoped runtime repair and regression gate for that existing credential UI path. The repair does not change database permissions or reveal transport: final browser reveal remains `crm_reveal_client_secret_value_v5` only.

Human acceptance also exposed an older-session re-auth conflict: an ADMIN could successfully create a 10-minute session-bound credential unlock while the underlying reveal helper still rejected Sessions older than 12 hours. Production migration `20260823045642 / credential_unlock_reauth_bridge` resolves only that conflict by accepting a still-valid unlock bound to the same Session, user, and workspace as sensitive-view re-auth. It does not refresh Session creation time, extend Session lifetime, broaden role access, change reveal throttles, or grant browser roles new EXECUTE privileges.

The BFFs additionally preserve only a small allowlist of safe credential error codes (for example credential reveal throttling) so the UI can distinguish expected security denials from generic upstream failures. Unknown upstream errors remain sanitized.

## Preflight state

Production read-only ACL inspection before Group 1 showed both functions had explicit ACL entries for `anon` and `service_role`, with no `PUBLIC` inheritance:

- `crm_unlock_credentials_v1`: `anon=true`, `authenticated=false`, `service_role=true`
- `crm_reveal_client_secret_value_v5`: `anon=true`, `authenticated=false`, `service_role=true`

The complete pre-P5 CRM function surface contained 12 anon-executable RPCs. Group 1 reduced this to exactly 10 while leaving `service_role` execution on all 40 CRM functions intact.

P0 isolated recovery rehearsal is PASS. P2-B server identity is PASS on both hosting paths. P3/P4 attack-style regression is merged and PASS. These are prerequisites for P5.

## Forward migration

`supabase/migrations/20260822_p5_revoke_sensitive_anon_exec.sql`

The permission migration contains exactly two permission changes:

```sql
revoke execute on function public.crm_unlock_credentials_v1(text, text) from anon;
revoke execute on function public.crm_reveal_client_secret_value_v5(text, text, text, text, text, text) from anon;
```

No other grant or object is modified by that migration.

The separate acceptance-discovered re-auth bridge is stored in:

`supabase/migrations/20260823_credential_unlock_reauth_bridge.sql`

Its rollback is independent of the permission rollback.

## Emergency rollback

`supabase/rollback/20260822_p5_restore_sensitive_anon_exec.sql`

The permission rollback restores exactly the two pre-P5 anon grants and nothing else. Use it only if either server-identity path fails after the revoke.

`supabase/rollback/20260823_credential_unlock_reauth_bridge_rollback.sql`

The re-auth rollback restores the previous sensitive-view freshness behavior without reopening anon EXECUTE.

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

The P3/P4 hard security gates remain PASS. The intentional permission gate `sensitive_anon_surface_pre_p5` is now `PASS_P5_COMPLETE`. The acceptance-discovered re-auth bridge changes one protected function definition without changing the inventory line count or the required privilege shape.

Final accepted post-Group-1 Production security fingerprint:

`258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e`

The earlier post-revoke/pre-reauth-bridge checkpoint was `258 / 4d6ab3cbfabc5f374fb97af6ca7ac5aaebc6632e1984da0b20182ff47f84d173`; it is retained only as an intermediate historical checkpoint and is not the final Group 1 fingerprint.

## Automated repository gates

`test_p5_sensitive_rpc_revocation.py` verifies:

- the permission migration has exactly two anon revokes;
- the exact two function signatures are targeted;
- no login/public/state/user-management RPC is revoked in Group 1;
- rollback has exactly the two inverse anon grants;
- the read-only check encodes the expected post-P5 privilege shape;
- both Cloudflare and Vercel BFFs still proxy the two sensitive RPC names through `GROWTHOPS_SUPABASE_SECRET_KEY` with no publishable-key fallback.

`test_session_security_migrations.py` verifies the credential re-auth bridge remains session/user/workspace bound, keeps the 10-minute unlock contract, and does not refresh/extend the CRM Session or weaken reveal throttling.

`test_http_only_session_api.js` verifies both BFFs keep server-cookie injection, v5-only scalar reveal, and safe credential error-code passthrough while unknown upstream errors remain sanitized.

`test_credential_eye_self_heal_output.py` additionally verifies the browser-only repair discovered during human acceptance:

- a stale reveal-installed marker is not trusted unless the real per-field eye button exists;
- if ADMIN unlock causes a card DOM replacement, the controller reacquires only the uniquely matching live account row;
- if scalar v5 reveal completes and the card is replaced again, the already-returned value may be rehydrated only for the same client + platform + account and only inside the original 10-second display window;
- the short-lived value is kept in memory only and is cleared on hide/background/navigation;
- no legacy broad reveal, v3 reveal, v4 reveal, `localStorage`, or `sessionStorage` credential path is restored.

Final shipped runtime audit confirms one canonical per-field eye installer/click handler and one `crm_reveal_client_secret_value_v5` browser call site; legacy reveal-button entry points are absent.

## Production execution record

1. Exact branch Preview gates passed before Production permission change.
2. Group 1 permission migration applied to Production as remote migration `20260822151709 / p5_revoke_sensitive_anon_exec_group1`.
3. Immediate privilege check passed: sensitive anon=0, authenticated=0, service_role=2; total anon CRM EXECUTE=10; service_role CRM EXECUTE=40.
4. Cloudflare and Vercel server-identity smoke remained normal after revoke; no permission rollback trigger observed.
5. Human testing exposed the older-Session re-auth conflict. The session-bound bridge was gated on both hosting paths and then applied to Production as `20260823045642 / credential_unlock_reauth_bridge`.
6. The bridge preserved the Group 1 privilege shape: CRM functions=40, anon EXECUTE=10, authenticated EXECUTE=0, service_role EXECUTE=40; CRM tables=9 and RLS-enabled CRM tables=9.
7. Repeated human testing temporarily hit the existing 10 reveals / 5 minutes safety throttle. The throttle was not weakened. Both BFFs were updated only to surface allowlisted credential security errors while continuing to sanitize unknown upstream errors.
8. Final canonical schema/security fingerprint after the accepted bridge is `258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e`.

## Human acceptance status

- Cloudflare Group 1 Preview login + refresh + real CRM state load: **PASS (user-attested)**.
- Vercel Group 1 Preview login + refresh + real CRM state load: **PASS (user-attested)**.
- ADMIN password unlock after revoke: **PASS (user-attested; backend audit also observed successful unlock events)**.
- Final scalar credential reveal on the current Cloudflare Group 1 path: **PASS (user-attested: value became visible and automatically returned to masked state after about 10 seconds)**.
- Browser connector independently observed the correct Group 1 page, ADMIN session, four per-field eye controls, and the exact-head Cloudflare deployment; it did not observe or record the revealed secret value.

All required Group 1 human gates are PASS. No password, 2FA value, unlock token, Session token, or revealed scalar value was shared into the acceptance record.

## Final merge sequence

1. Require the exact final Group 1 branch head green on Vercel and Cloudflare.
2. Re-check PR/head/main, Production privilege snapshot, P3/P4 hard gates, and final `258`-line Production fingerprint.
3. Mark PR Ready and merge only with the expected head SHA.
4. Verify merged `main`, Production deployment behavior, privileges, and fingerprint before starting Group 2 execution.

## Rollback trigger

Run the permission rollback immediately if either Cloudflare or Vercel cannot execute either sensitive RPC through the server-only identity while `service_role` privilege is expected to remain present. A browser-only rendering defect is **not** a permission rollback trigger when server identity and the two sensitive RPCs are demonstrably functioning; fix and re-validate the UI separately.

If the session-bound re-auth bridge itself causes a security or functional regression, use its independent rollback; do not restore anon EXECUTE unless the permission rollback trigger is independently met.

## Later P5 groups

Do not combine later revokes into Group 1. Groups 2–6 remain separate preparation PRs and must not be applied or merged ahead of their predecessors. `crm_login_v3` and `crm_public_status` remain a separate final public-boundary group.
