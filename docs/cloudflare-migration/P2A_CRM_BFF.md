# P2-A Cloudflare CRM BFF Port

Last updated: 2026-08-22

## Scope

P2-A ports the existing Vercel same-origin `/api/crm` BFF behavior 1:1 to Cloudflare Pages Functions.

This phase does **not**:
- introduce a service-role or other privileged Supabase identity;
- revoke any Supabase `anon` RPC grants;
- split `/api/crm` into multiple endpoints;
- change CRM session duration or cookie semantics;
- broaden credential reveal beyond `crm_reveal_client_secret_value_v5`;
- sanitize upstream error messages (reserved for P2-B);
- change CSP, WAF, Access, production DNS, or the real CRM custom domain.

The Vercel `api/crm.js` implementation remains unchanged and available as the rollback reference.

## Cloudflare implementation

Cloudflare Pages Function:

`functions/api/crm.js` → `/api/crm`

Behavior preserved from Vercel:
- POST only; non-POST returns 405 and `Allow: POST`;
- `sec-fetch-site` / Origin same-origin checks;
- strict RPC allowlist;
- `__Host-growthops_crm` cookie;
- `Path=/; Max-Age=604800; HttpOnly; Secure; SameSite=Strict`;
- login response token removed from browser-visible JSON and stored in the cookie;
- browser-provided `p_token` is removed or overwritten by the cookie session token;
- authenticated routes require a cookie session;
- logout clears the cookie even when the upstream logout request fails;
- credential reveal is restricted to scalar `crm_reveal_client_secret_value_v5`;
- v3/v4/full secret-bundle reveal RPCs are not allowlisted;
- P2-A continues using the existing publishable-key Supabase boundary so privilege tightening can occur later under P2-B/P5 after both Cloudflare and Vercel server identities are proven.

## Automated parity gate

`test_cloudflare_p2a_api.mjs` runs both the Vercel handler and the Cloudflare handler against the same request cases and compares status/body/header/cookie/upstream-request behavior.

Covered cases:
- GET → 405;
- cross-site and wrong-Origin rejection;
- invalid JSON;
- non-allowlisted RPC rejection;
- v3/v4/full credential reveal rejection;
- login token stripping and exact cookie semantics;
- missing-session rejection and cookie clearing;
- cookie token overriding forged browser `p_token`;
- v5 scalar credential reveal;
- logout cookie clearing on success and upstream failure.

The gate is part of `build.sh` and emits:

`CLOUDFLARE_P2A_API_PARITY_TESTS_OK: method=post-only; csrf=same-origin; allowlist=exact; login-token-hidden; cookie-injection=exact; credential-reveal=v5-only; logout-clears-cookie`

## Live Preview acceptance evidence

Initial accepted P2-A implementation head before final squash:

`ff32e84b151f293d945bea24d7cc4726f0dce778`

Cloudflare Preview:

`https://d9a367dd.growthops-crm.pages.dev`

Deployment ID:

`d9a367dd-77b7-4f84-b7a0-788011bf8da8`

Cloudflare deployment status: `success`.

Cloudflare routing configuration confirmed exactly one Function route:

`/api/crm` → `api/crm.js:onRequest`

Invocation include list contained `/api/crm`.

Live GET acceptance:
- `GET /api/crm` returned `{"message":"METHOD_NOT_ALLOWED"}` through the deployed Function.

A temporary no-secret browser smoke page was deployed only for acceptance and then removed before final squash. From the same Cloudflare Preview origin it performed real POST requests to the deployed `/api/crm` Function:
- `crm_public_status` → HTTP 200 with `{ "service": "GrowthOps CRM Cloud", "initialized": true }`;
- `crm_not_allowed` → HTTP 403 with `RPC_NOT_ALLOWED`;
- `crm_load_state_v3` without session cookie → HTTP 401 with `SESSION_REQUIRED`.

The temporary smoke page and its temporary build copy hook were deleted after validation and are not part of the intended final P2-A diff.

Vercel Preview for the same P2-A implementation was `READY`, and its build log emitted `CLOUDFLARE_P2A_API_PARITY_TESTS_OK`. Existing frozen CRM build/security hashes remained unchanged.

## Remaining P2-A acceptance before merge

Before merging the final single-commit P2-A candidate:
1. squash the P2-A branch to one commit on the current `main`;
2. require the squashed head to be green on both Vercel and Cloudflare;
3. confirm Cloudflare final-head routing still exposes only `/api/crm`;
4. perform one user-entered login on the final Cloudflare Preview (the user must enter credentials themselves; credentials must not be sent to ChatGPT), confirm state loads, then log out;
5. re-run the Production Supabase schema/security fingerprint and require `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`;
6. only then mark the P2-A PR Ready and merge with the expected head SHA.

## Next phase

P2-B, not P2-A, establishes the true server-only Supabase identity boundary on both Cloudflare and Vercel, adds request IDs/log filtering/error sanitization, and prepares for incremental P5 revocation of remaining `anon` RPC execution grants.
