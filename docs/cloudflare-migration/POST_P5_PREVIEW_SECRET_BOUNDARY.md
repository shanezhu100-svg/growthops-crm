# Post-P5 Preview Server-Secret Boundary

Status: build/runtime guard verified; automatic Vercel non-main Git deployment path hardened; platform secret-scope cleanup still required.

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

## Observed Vercel evidence

Vercel Preview secret scope is **verified open**, not unverified.

On 2026-08-23 a Vercel Preview reached the build command and was rejected immediately by the guard because a server secret was present without an isolated staging Supabase URL. The guard printed only the safe boundary error and did not print the secret value.

The same platform state was revalidated on 2026-08-25 using PR #85. Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` for branch `docs/current-recovery-concurrency-20260825` / commit `f162f675d5cf606f3659ad5f363ca68e3702ffa6` failed at `sh build.sh` with:

`PREVIEW_SECRET_BOUNDARY_FAILED: Preview deployment has a server secret but no explicit staging Supabase URL.`

This confirms that the Vercel Preview environment still had a server secret in scope and no accepted isolated staging URL. No secret value is recorded in this document.

## Observed Cloudflare evidence

Cloudflare Dashboard verification on 2026-08-25 showed that the Preview environment still had a `GROWTHOPS_SUPABASE_SECRET_KEY` binding. No secret value is recorded here. With no accepted isolated staging URL, the repository guard correctly rejects a usable Preview backend rather than defaulting to Production Supabase.

The connected browser interface available during this review was read/navigation-only and did not provide form mutation, so the binding could not be removed through the connected tool. This is an operational write-access blocker, not a reason to weaken the guard.

## Automatic Vercel Preview deployment mitigation

The repository also prevents normal non-main Git deployments on Vercel so pull requests rely on the secret-free GitHub CRM Build Gate instead of executing arbitrary branch code in a Preview environment.

A configuration defect was identified on 2026-08-25: the previous default-deny rule used bare minimatch `*`, while recent PR branches used slash-containing names such as `docs/...`. Those branches still produced Vercel Preview deployments and reached the secret boundary guard.

PR #86 changed `vercel.json` to the slash-safe policy:

- `"**": false`
- `"main": true`

and updated `test_ci_quota_guard.py` so the bare-star form cannot silently return.

Live acceptance evidence for PR #86:

- slash-containing branch: `ops/vercel-preview-globstar-20260825`;
- PR head: `62b06895501628c02072ac810cd1ad59fcacdca5`;
- CRM Build Gate run #76: completed / success;
- no new Vercel Preview deployment was created for the branch during the acceptance observation window;
- merged `main`: `91c0edcb24b79d282faa72d7d83435a1e1265d30`;
- merged-main CRM Build Gate run #77: completed / success;
- Vercel Production deployment `dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6`: `READY`.

This materially reduces Preview secret exposure through normal Git PR activity, but it does **not** prove the Preview-scoped platform secret has been removed. Manual/CLI/API Preview deployments could still consume that environment scope if created. Platform secret separation therefore remains required.

## Platform cleanup still required

The build guard and Git deployment policy are defense in depth, not the final secret-management control. A repository writer with another Preview execution path must not be able to obtain a Production credential from platform Preview scope.

Final platform remediation remains:

- Cloudflare Pages Preview: remove `GROWTHOPS_SUPABASE_SECRET_KEY`, unless/until an isolated staging Supabase project is configured.
- Vercel Preview: remove Preview from the target scope of `GROWTHOPS_SUPABASE_SECRET_KEY`; keep Production only.
- If Preview backend testing becomes necessary, provision a separate staging Supabase project and set both Preview URL and Preview secret to that project.

Do not create or reuse Production credentials merely to make Preview green.

## Acceptance

A complete acceptance requires all of the following:

- Production build with the Production server secret remains green;
- normal non-main Vercel Git branches do not run Preview deployments under the current main-only deployment policy;
- Cloudflare Preview with no server secret passes the boundary guard and `/api/crm` fails closed;
- Vercel Preview with no server secret passes the boundary guard and `/api/crm` fails closed when an intentional isolated Preview is created;
- a simulated Preview + Production target is rejected before any application build step;
- no guard output contains secret material;
- Cloudflare/Vercel platform configuration no longer injects the Production secret into Preview.

Until the final platform-scope item is verified on both providers, this control remains **partially accepted**.
