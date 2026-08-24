# Post-P5 Preview Server-Secret Boundary

Status: build guard verified; platform environment cleanup still required.

## Threat model

The CRM Pages/Vercel server bridge uses `GROWTHOPS_SUPABASE_SECRET_KEY` as a privileged server identity. Preview deployments are untrusted relative to production because arbitrary branch code is built and executed there. A production server secret available to Preview therefore expands the blast radius of a malicious or accidental branch change even when the browser RPC surface is fully revoked.

This is especially important on Cloudflare Pages because Preview environment variables are available during both build and runtime. Runtime-only checks cannot prevent build-time branch code from reading an injected production secret.

## Required invariant

Production may use the production Supabase server secret and the canonical production project:

- canonical production URL: the `supabaseUrl` in `public-runtime-config.json`
- production branch: `main`

Preview must use one of two modes only:

1. **Backend disabled** — `GROWTHOPS_SUPABASE_SECRET_KEY` is absent. The static Preview may build, while `/api/crm` fails closed with `503 SERVER_IDENTITY_NOT_CONFIGURED`.
2. **Backend isolated** — Preview has a server secret only when `GROWTHOPS_SUPABASE_URL` is explicitly set to a different HTTPS `*.supabase.co` project. This supports a future staging Supabase project without weakening the guard.

Preview is rejected when a server secret is present and:

- `GROWTHOPS_SUPABASE_URL` is absent (the runtime default is production),
- the URL resolves to the canonical production Supabase host, or
- the URL is malformed/non-HTTPS/non-Supabase, embeds credentials/a nonstandard port, or contains a path/query/fragment.

## Build enforcement

`preview_secret_guard.py` runs before all other build stages. It recognizes:

- Cloudflare Preview: `CF_PAGES=1` and `CF_PAGES_BRANCH != main`
- Cloudflare unknown branch context: `CF_PAGES=1` with a missing branch is treated conservatively as Preview-like
- Vercel Preview: `VERCEL_ENV=preview`

It never prints the server secret. `test_preview_secret_guard.py` exercises production, backend-disabled Preview, production-target rejection, staging isolation, malformed URL rejection, missing Cloudflare branch behavior, and output leak protection.

## Observed Vercel acceptance evidence

On 2026-08-23 the exact-head Vercel Preview for commit `a6788d91ee67adcf7137f75ae52ef67c41659556` reached the build command and was rejected immediately by the guard:

`PREVIEW_SECRET_BOUNDARY_FAILED: Preview server secret is set but GROWTHOPS_SUPABASE_URL is absent; runtime would default to production`

This is expected and confirms the platform still injects a server secret into Preview while the BFF would otherwise default to the production Supabase project. No secret value was printed.

## Platform cleanup still required

The build guard is defense in depth, not the final secret-management control. A repository writer could remove a build-time guard in the same branch that tries to read the secret. The final control is platform-side environment separation:

- Cloudflare Pages Preview: remove `GROWTHOPS_SUPABASE_SECRET_KEY`, unless/until an isolated staging Supabase project is configured.
- Vercel Preview: remove Preview from the target scope of `GROWTHOPS_SUPABASE_SECRET_KEY`; keep Production only.
- If Preview backend testing becomes necessary, provision a separate staging Supabase project and set both Preview URL and Preview secret to that project.

Do not create or reuse production credentials merely to make Preview green.

## Acceptance

A complete acceptance requires all of the following:

- production build with the production server secret remains green;
- Cloudflare Preview with no server secret passes the boundary guard and `/api/crm` fails closed;
- Vercel Preview with no server secret passes the boundary guard and `/api/crm` fails closed;
- a simulated Preview + production target is rejected before any application build step;
- no guard output contains secret material;
- Cloudflare/Vercel platform configuration no longer injects the production secret into Preview.

Until the last item is verified, this control remains **partially accepted**.
