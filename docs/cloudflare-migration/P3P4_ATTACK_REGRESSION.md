# P3/P4 Attack-Style Regression

Last updated: 2026-08-22

## Scope

P3/P4 is regression-only. It does **not** redesign or change CRM Session, Vault, Credential reveal, business UI, database schema, RPC grants, CSP, WAF, Access, DNS, or traffic routing.

The phase adds attack-oriented automated tests and a read-only live Supabase inventory. Production customer secrets are not read, copied, decrypted, logged, or placed in test fixtures.

## Attack matrix

`test_cloudflare_p3p4_attack_regression.mjs` exercises both the Vercel rollback BFF and the Cloudflare Pages Function with synthetic data only. It verifies:

- a cross-origin request remains blocked even when a valid-looking HttpOnly Cookie is present;
- browser-forged `p_token` cannot authenticate without the HttpOnly Cookie;
- when a Cookie exists, any body `p_token` is replaced by the Cookie session token;
- historical v3/v4/full credential reveal and internal Vault helper RPC names are rejected by the BFF allowlist before upstream execution;
- unlock/reveal/user-management/state RPCs require the HttpOnly session boundary;
- malicious or oversized `X-Request-ID` values are not reflected, while safe IDs round-trip;
- malformed JSON is rejected before any backend call;
- array/non-object `args` cannot smuggle a forged token;
- login failures or missing upstream session tokens do not leak a token or create a session Cookie;
- raw upstream password/2FA/secret text is sanitized from browser responses and structured logs;
- upstream session failures clear the browser Cookie;
- an upstream logout failure still clears the browser Cookie.

Success marker:

`CLOUDFLARE_P3P4_ATTACK_REGRESSION_OK: cross-origin=blocked; forged-token=blocked; broad-reveal=blocked; request-id-injection=filtered; upstream-errors=sanitized; logout-failure=clears-cookie`

Vercel Preview on the initial attack-regression head emitted this marker and retained all frozen CRM/browser artifact hashes.

## Live Supabase read-only checks

`supabase/baseline/p3p4_attack_regression.sql` is read-only and validates the Production security shape without reading Vault values or CRM session tokens.

The live check on 2026-08-22 returned the following hard-gate results:

- `all_crm_tables_rls_enabled`: PASS — 9/9 CRM tables have RLS enabled;
- `anon_authenticated_direct_table_grants_absent`: PASS — 0 direct grants;
- `authenticated_crm_execute_absent`: PASS — 0/40 CRM functions executable by `authenticated`;
- `service_role_exec_all_crm_functions`: PASS — 40/40 executable by `service_role`;
- `broad_reveal_anon_blocked`: PASS — v3, v4, and full reveal are blocked from `anon`/`authenticated` and remain server-only;
- `vault_helpers_browser_roles_blocked`: PASS — workspace Vault read/write helpers are blocked from browser roles and remain server-only;
- `unlock_v1_admin_password_throttle_constraints`: PASS — ADMIN, current-password, failure-count, and throttle constraints remain in source;
- `reveal_v5_admin_unlock_field_binding`: PASS — ADMIN, password/twofa field allowlist, unlock/session/user/workspace binding, and expiry checks remain in source;
- `user_management_session_workspace_guards`: PASS — the four user-management/safe-summary RPCs retain session/workspace/ADMIN guards;
- `save_state_session_and_secret_guard`: PASS — session plus secret redaction/extraction controls remain present.

The only non-PASS result is intentional and deferred:

- `sensitive_anon_surface_pre_p5`: `PENDING_P5` — `crm_unlock_credentials_v1` and `crm_reveal_client_secret_value_v5` are still anon-executable until the separate P5 permission-revocation phase.

The first dry execution of the read-only inventory exposed a test-only PostgreSQL type mismatch (`name[]` vs `text[]`) in its expected-list comparison. The query performed no writes. The script was corrected by explicitly casting `proname` to `text`, then rerun successfully with the results above.

No grant or permission change is made in P3/P4.

## Acceptance gates

Before this phase can be marked Ready or merged:

1. Vercel Preview must pass the existing build/security suite plus the new P3/P4 attack marker;
2. Cloudflare Preview must pass the same final branch head;
3. the live read-only Supabase attack inventory must return `PASS` for every hard gate and only `PENDING_P5` for the explicitly deferred sensitive anon surface;
4. the Production schema/security fingerprint must remain exactly `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`;
5. the final diff must contain tests/read-only inventory/docs/build-gate only, with no runtime, database migration, Secret, Session, Vault, or permission change;
6. the branch must be one final commit, ahead 1 / behind 0;
7. only after the exact final head is green on both platforms may the Draft PR be marked Ready and merged with expected head SHA.

## Next phase

P5 is separate. It will incrementally revoke the remaining sensitive anon EXECUTE grants, starting with:

- `crm_unlock_credentials_v1`;
- `crm_reveal_client_secret_value_v5`.

Each P5 revoke group must validate both Cloudflare and Vercel rollback paths before proceeding.
