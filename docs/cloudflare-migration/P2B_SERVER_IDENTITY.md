# P2-B Server-Side Supabase Identity

Last updated: 2026-08-22

## Scope

P2-B hardens both rollback paths without changing CRM business behavior:

- Cloudflare Pages Function `/api/crm`;
- Vercel `/api/crm` rollback BFF;
- modern Supabase backend-only secret key identity;
- request IDs;
- filtered structured logs;
- sanitized upstream error responses.

P2-B does **not** revoke Supabase `anon` RPC grants. Incremental RPC revocation remains P5 and starts only after both Cloudflare and Vercel server identities are proven in real Preview/Production acceptance.

P2-B also does not change CSP, WAF, Cloudflare Access, DNS, session duration, credential reveal design, or CRM UI/business logic.

## Server identity contract

Both BFF implementations accept exactly one server credential variable:

`GROWTHOPS_SUPABASE_SECRET_KEY`

The value must use the modern Supabase backend-only `sb_secret_...` format.

There is no publishable-key fallback. A valid allowlisted RPC request fails closed with HTTP 503 and `SERVER_IDENTITY_NOT_CONFIGURED` when the server secret is absent or malformed.

The real secret key must never be committed to GitHub, printed in logs, placed in URLs, copied into ordinary backups, or sent through ChatGPT. It is entered directly into each hosting platform's encrypted Secret / Environment Variable UI.

## Preserved BFF behavior

The exact P2-A application boundary remains in place:

- POST only;
- same-origin request guard;
- exact RPC allowlist;
- `__Host-growthops_crm` HttpOnly/Secure/SameSite=Strict cookie;
- 7-day cookie Max-Age;
- login token stripped from browser JSON;
- browser `p_token` removed or overwritten by cookie session token;
- authenticated calls require the HttpOnly cookie;
- credential reveal remains only `crm_reveal_client_secret_value_v5`;
- v3/v4/full bundle reveal RPCs remain blocked by the BFF allowlist;
- logout clears the session cookie and calls server-side `crm_logout`.

## Request IDs

Every BFF response includes `X-Request-ID`.

A safe incoming `X-Request-ID` is preserved when it contains only `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, or `-` and is 8–128 characters long. Otherwise the server generates a new ID.

## Log filtering and error sanitization

The BFF emits only structured error metadata: event name, platform, request ID, allowlisted RPC name (otherwise `unknown`), and numeric HTTP status.

It does not intentionally log RPC arguments, request/response bodies, cookies, CRM session tokens, passwords, 2FA values, unlock tokens, Supabase secret keys, or raw upstream database error text.

Browser-facing upstream errors are sanitized to fixed messages. The live error probe confirmed an upstream 404 is returned only as `404 UPSTREAM_NOT_FOUND` with the request ID preserved.

## Automated gate

`test_cloudflare_p2b_api.mjs` uses synthetic test-only values and never needs a real Supabase secret. It verifies server-secret enforcement, no publishable fallback, request IDs, login token stripping, cookie behavior, forged `p_token` replacement, v5-only reveal, logout clearing, upstream error sanitization, and log filtering.

Success marker:

`CLOUDFLARE_P2B_SERVER_IDENTITY_TESTS_OK: secret-key=required; publishable-fallback=none; request-id=active; logs=filtered; errors=sanitized; v5-only; logout-clears-cookie`

Existing frozen CRM/browser artifact hashes remain unchanged.

## Platform configuration and live acceptance

`GROWTHOPS_SUPABASE_SECRET_KEY` is configured directly in the hosting dashboards without exposing the value to GitHub, URLs, logs, or ChatGPT:

- Vercel: `Production and Preview`;
- Cloudflare Pages Production: type `Secret`;
- Cloudflare Pages Preview: type `Secret`.

Live secret-backed Preview acceptance passed on both platforms:

- Cloudflare: `crm_public_status` = 200, missing-session protected RPC = 401, non-allowlisted RPC = 403;
- Vercel rollback Preview: the same 200 / 401 / 403 behavior;
- `X-Request-ID` round-tripped on all probes;
- pre-fix Cloudflare Preview correctly failed closed with 503 while its Preview Secret was absent;
- after Preview Secret configuration, Cloudflare returned 200 through the server-secret identity;
- Vercel runtime error log for the probe contained only `{event, platform, requestId, rpc, status}`;
- Vercel log searches found no `sb_secret_`, `password`, `twofa`, or CRM Session Cookie marker;
- Cloudflare's current account-level Observability view exposed no Pages Function runtime events, so no claim is made that Cloudflare runtime log contents were directly inspected. Code-level filtering and the live Vercel log format are verified.

Real Cloudflare Branch Preview session acceptance also passed:

- Supabase audit recorded a successful `LOGIN` for the real CRM login attempt;
- the Branch Preview loaded the authenticated CRM workspace through the HttpOnly-session path;
- after logout, the Branch Preview returned to the login state and showed `未登录` with cleared workspace data;
- the session created by that successful login no longer existed in `crm_sessions` after logout;
- remaining active sessions for the same user predated this acceptance login and were not created by this test.

No password, CRM session token, unlock token, 2FA value, or Supabase secret value was read during validation.

Production Supabase schema/security fingerprint after runtime acceptance remained exactly:

`258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`

The temporary runtime smoke page and build hook were removed. The cleaned working head then built successfully on both Vercel Preview and Cloudflare Preview with the P2-B automated gate still passing.

## Final merge gate

Before merge:

1. squash the branch to one final commit containing only the intended P2-B files;
2. require that exact final head to be green on Cloudflare and Vercel;
3. re-run the Production Supabase schema/security fingerprint and require the frozen `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729` result;
4. do **not** revoke `anon` RPC grants in P2-B;
5. only then mark Draft PR #19 Ready and merge using the expected final head SHA.

## Next phase

P5 incrementally removes remaining `anon` RPC execution only after this server-identity boundary is proven on both Cloudflare and Vercel. The first sensitive revoke group is planned for:

- `crm_unlock_credentials_v1`;
- `crm_reveal_client_secret_value_v5`.

Each P5 revoke group must validate both Cloudflare and Vercel rollback paths before continuing.
