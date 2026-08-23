# P5 Group 4 — Credential Safe Summary Privilege Hardening

Last updated: 2026-08-23

## Status

Groups 1–3 predecessor gates are complete. Group 4 Production execution is complete and verified. The only database privilege change was removal of `anon` EXECUTE from exactly one server-mediated credential safe-summary RPC.

This branch is based directly on accepted `main@b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89` pending the final evidence-head merge.

## Exact scope

Group 4 contains exactly one live RPC:

- `crm_client_account_safe_summary(text,text)`

This remains a final-runtime dependency. The credential UI uses it to render login identifiers plus credential-presence booleans without returning password or 2FA plaintext.

## Accepted predecessor baseline

Immediately before Group 4, Production was verified as:

- `main`: `b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89`;
- CRM functions: `40`;
- anon EXECUTE: `6`;
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec`;
- canonical fingerprint: `258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3`.

The exact target was `SECURITY DEFINER`, `anon=true`, `authenticated=false`, `service_role=true`, and `PUBLIC EXECUTE=false`.

## BFF/runtime security boundary

Both Vercel and Cloudflare `/api/crm` BFFs continue to:

- classify the RPC under `AUTH_RPCS`, never `PUBLIC_RPCS` or `LOGIN_RPCS`;
- require the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict session cookie;
- reject a missing cookie with `401 SESSION_REQUIRED` before any upstream call;
- overwrite browser-supplied `p_token` with the server-read cookie token;
- require `GROWTHOPS_SUPABASE_SECRET_KEY` with `sb_secret_` identity and no publishable-key fallback;
- enforce same-origin before dispatch.

The final shipped credential runtime still depends on `crm_client_account_safe_summary` and keeps retired `crm_client_credential_status` out of runtime.

## Function safeguards verified before execution

Read-only Production inspection confirmed that the exact function:

- is `SECURITY DEFINER`;
- calls `crm_session_context`;
- remains workspace-scoped;
- permits only ADMIN/OPS;
- reads the workspace secret tree only to derive credential-presence flags;
- does not call a `crm_reveal*` RPC;
- returns identifiers plus `hasPassword` / `has2FA` booleans;
- does not return `password`, `2fa`, `loginPassword`, `login_password`, or generic `value` output keys.

No Vault plaintext was read or returned during this audit.

## Execution-package exact-head evidence

Execution-package head:

`c8ef33d2dec3993a122fd960e0e6c284a8ef51e6`

Vercel:

- deployment `dpl_9WJ66t9iVaNyx9SGWZr9MWDHXbpx`;
- state `READY`;
- `P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK` PASS;
- `P5_GROUP4_SAFE_SUMMARY_BFF_OK` PASS;
- `P5_GROUP4_SAFE_SUMMARY_REVOCATION_OK` PASS;
- predecessor Group 1–3 gates and P3/P4 attack regression remain PASS.

Cloudflare Pages:

- deployment `32b8f3be-b447-4403-a93d-1867182f68aa`;
- URL `https://32b8f3be.growthops-crm.pages.dev/`;
- status `success`;
- same exact commit `c8ef33d2dec3993a122fd960e0e6c284a8ef51e6`;
- Group 4 candidate/BFF/revocation gates PASS;
- P3/P4 attack regression PASS;
- P1 output parity PASS.

## Production migration

Forward migration file:

`supabase/migrations/20260823_p5_group4_revoke_safe_summary_anon_exec.sql`

Applied Production migration record:

`20260823071407 / p5_group4_revoke_safe_summary_anon_exec`

Exact privilege change:

```sql
revoke execute on function public.crm_client_account_safe_summary(text, text) from anon;
```

Exact inverse rollback is preserved in:

`supabase/rollback/20260823_p5_group4_restore_safe_summary_anon_exec.sql`

Read-only post-check is preserved in:

`supabase/baseline/p5_group4_safe_summary_anon_exec_check.sql`

## Production post-change verification

The exact target now has:

- `anon=false`;
- `authenticated=false`;
- `service_role=true`.

Global Production state is now:

- CRM functions: `40`;
- anon EXECUTE: `5` (`6 -> 5`);
- authenticated EXECUTE: `0`;
- service_role EXECUTE: `40`;
- CRM tables with RLS: `9/9`;
- latest migration: `20260823071407 / p5_group4_revoke_safe_summary_anon_exec`.

Canonical inventory remains exactly 258 lines. The repository-frozen algorithm in `supabase/baseline/p0_schema_security_fingerprint.sql` was independently calibrated by simulating the pre-Group-4 target grant; that simulation reproduced the accepted Group-3 fingerprint exactly. Post-Group-4 fingerprint:

`258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`

The fingerprint delta is expected from exactly one `FPRIV` transition.

## Automated gates

`test_p5_group4_safe_summary_candidate.py` enforces the authenticated-only BFF route, final-runtime dependency, narrow output contract, database definition safeguards, accepted Group-3 baseline, exact execution-package evidence, applied migration, post-change anon total, and canonical fingerprint.

`test_p5_group4_safe_summary_bff.mjs` executes the path against both handlers and proves no-session rejection with zero upstream calls plus authoritative cookie-token substitution.

`test_p5_group4_safe_summary_revocation.py` enforces the one-RPC forward migration, exact inverse rollback, read-only post-check, and preserved BFF/session boundary.

Expected markers:

`P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK: safe-summary=auth-only-bff+final-runtime; output=identifier+presence-booleans-only; reveal-call=none; group3=accepted; production-change=applied+verified`

`P5_GROUP4_SAFE_SUMMARY_BFF_OK: no-session=401+zero-upstream; cookie-token=authoritative; both-platforms=pass`

`P5_GROUP4_SAFE_SUMMARY_REVOCATION_OK: revoke=1-safe-summary-anon-only; rollback=1-exact-grant; post-check=read-only; auth-bff=session-gated; expected-anon=5; service-role=40`

## Final merge gate

Before merging PR #24, the final evidence-only head must independently pass Vercel and Cloudflare builds with Group 1–4 gates, P3/P4 attack regression, and Cloudflare P1 parity green.

Merge must use the expected final head SHA. After merge, verify `main`, Vercel Production, Cloudflare Production, Production `40 / 5 / 0 / 40`, RLS `9/9`, latest migration `20260823071407`, and canonical fingerprint `258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b`.

## Non-goals

Group 4 does not change credential values, reveal/unlock behavior, login/state/user-management behavior, Vault contents, database function bodies, tables, RLS, policies, session duration, CSP, DNS, WAF, CRM UI/business behavior, or Groups 5–6 privileges.
