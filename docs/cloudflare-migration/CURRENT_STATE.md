# GrowthOps CRM Current State

Last reviewed: 2026-08-24

This file is the **current-state authority** for the CRM hosting/security migration. Phase documents in this directory (P0, P1, P2-A, P2-B, P3/P4, P5, and Post-P5) are retained as implementation and acceptance evidence; when a phase document describes a future step that has since been completed, this file and the current canonical build gates take precedence.

## Current application boundary

The browser uses a same-origin CRM backend-for-frontend at `/api/crm` on both supported hosting paths:

- Vercel: `api/crm.js`;
- Cloudflare Pages Functions: `functions/api/crm.js`.

The browser does not receive or use a Supabase publishable URL/key configuration for direct CRM RPC access. Browser RPC traffic goes through the same-origin BFF.

Both BFFs require the server-only `GROWTHOPS_SUPABASE_SECRET_KEY` identity for allowlisted upstream RPC execution; there is no publishable-key fallback. Production Supabase origin selection is pinned to the canonical project and invalid/mismatched Production targets fail closed before upstream fetch.

## Session and request boundary

Current enforced behavior includes:

- POST-only `/api/crm` action execution;
- same-origin CSRF/origin checks;
- exact RPC allowlist;
- `__Host-growthops_crm` session cookie with HttpOnly, Secure, SameSite=Strict and 7-day Max-Age;
- login token removed from browser-visible JSON and moved into the HttpOnly cookie;
- forged body `p_token` cannot override the cookie session;
- logout clears the browser session even when upstream logout fails;
- request IDs are constrained/filtered and upstream errors are sanitized;
- credential reveal is v5 single-scalar only;
- ADMIN credential unlock/reveal remains session/user/workspace bound with the accepted reauthentication/throttle behavior.

Current input/resource guards include a 4 MiB API body limit, top-level object request envelope, UTF-8 byte bounds for login/admin/unlock passwords and user identity fields, and a bounded session-token contract. The canonical tests are authoritative for exact limits and failure semantics.

## Current Supabase privilege state

The canonical repository gates encode the accepted post-P5 Production privilege shape:

- CRM `anon` RPC EXECUTE: `0` after P5 Group 6;
- browser `authenticated` CRM RPC execution remains absent;
- Post-P5 service-role RPC minimization preserves the reviewed BFF/bootstrap entry surface and reports `service-role=12`;
- direct service-role CRM table grants are removed;
- direct service-role sequence grants are removed;
- RPC entry paths preserve the required SECURITY DEFINER wrapper chain;
- CRM ACL event guards cover create/alter of `public.crm_*` objects;
- RLS-alter guards cover the protected CRM table namespace;
- browser roles remain blocked from sensitive credential/Vault internals.

Do not restore `anon` RPC execution or broad service-role relation access as a normal hosting rollback. Use the exact migration-specific rollback process in `ROLLBACK.md` only for a diagnosed database-control regression.

## Current credential/storage boundary

- customer password/2FA secret values remain in Supabase Vault-backed server-side handling;
- browser credential reveal uses `crm_reveal_client_secret_value_v5` single-value transport only;
- broad v3/v4/full reveal is blocked from the browser path;
- revealed scalar values are ephemeral in memory and are cleared on the accepted timeout/background/navigation behavior;
- workspace state has a hard secret-material guard;
- normal CRM backups must not include customer password/2FA values;
- customer secrets must not be copied to Pages, Workers KV, D1, R2, logs, GitHub, or ordinary backups.

## Current build and merge authority

The canonical local/CI build is:

`sh build.sh && python3 cloudflare_p1_verify.py`

GitHub Actions is the PR hard gate and runs without CRM/Supabase secrets. Its current quota/security contract includes:

- `contents: read` token permissions;
- checkout credentials not persisted;
- SHA-pinned GitHub Actions;
- Node 24;
- no CRM/Supabase secrets in the PR runner;
- complete canonical CRM build/security regression suite;
- final Cloudflare artifact/output parity verification.

A change is not considered merge-safe merely because it is documentation-only or because one hosting platform deploys. The expected workflow remains: isolated branch → narrow diff → canonical gate → inspect final parity marker → merge with expected head SHA → verify resulting Production deployment.

## Hosting/deployment policy

### Vercel

`vercel.json` is default-deny for non-main Git deployments and enables Git deployment for `main` only. This protects Hobby deployment quota. Pull requests therefore rely on the secret-free GitHub canonical gate; merged `main` triggers Vercel Production.

The stable Vercel application alias is:

`https://growthops-crm.vercel.app`

For rollback, do not permanently pin an ancient pre-P5 build. Use a READY, gate-accepted `main` Production deployment compatible with the current database privilege state. See `ROLLBACK.md`.

### Cloudflare Pages

The Cloudflare Pages project uses `main` as the Production branch and the same canonical build/output contract. `cloudflare_p1_verify.py` requires deterministic parity for the pinned production artifacts and also guards the inert top-level 404 and static security headers.

Cloudflare Preview must not silently use Production Supabase. Standard Pages Preview hosts require an explicit isolated staging `GROWTHOPS_SUPABASE_URL` when a server secret is active; otherwise the runtime is expected to fail closed. Do not weaken the origin guard to make Preview pass.

## Security headers / static fail-closed behavior

The canonical gate verifies parity between Vercel security-header policy and Cloudflare output/function responses. Unknown top-level static paths use an inert, script-free 404 instead of an active SPA fallback that could expose CRM runtime material on unintended paths.

Current CSP still preserves the inline/runtime compatibility required by the existing shipped frontend. Tightening CSP further is a separate frontend/dependency project and must not be done by deleting required canonical build assets or weakening the output parity gate.

## Recovery authority

Operational rollback instructions are in:

`ROLLBACK.md`

The core rule is: **hosting rollback and database privilege rollback are separate operations**. Route back to a compatible validated Vercel server-boundary build first; change Supabase privileges only when a specific database security migration is proven to be the cause, and then only through its exact reviewed rollback artifact.

## Historical phase documents

Use phase documents for detailed evidence:

- `P0_*.md`: recovery/fingerprint baseline and isolated restore proof;
- `P1_*.md`: initial Cloudflare static Pages parity/Preview acceptance;
- `P2A_CRM_BFF.md`: first `/api/crm` Cloudflare parity port;
- `P2B_SERVER_IDENTITY.md`: server-only Supabase identity, request IDs, log filtering and error sanitization;
- `P3P4_ATTACK_REGRESSION.md`: attack-style BFF regression and pre-P5 inventory;
- `P5_*.md`: incremental `anon` RPC revocation history;
- `POST_P5_*.md`: service-role minimization, relation ACL, trusted-source login buckets, ACL/RLS guards and later input/schema invariants.

Those documents intentionally preserve the state observed at their own phase. Their historical fingerprints, grant counts, “next phase” sections, or Preview assumptions must not be interpreted as the current Production contract when they differ from this file or the canonical build gates.

## Current maintenance rules

1. Prefer small, single-purpose PRs with explicit rollback and no unrelated refactors.
2. Do not delete files solely because their names look historical; prove they are outside build, CI, runtime and documentation dependencies first.
3. Do not weaken fail-closed Preview/Production origin checks to accommodate platform configuration gaps.
4. Do not reintroduce browser Supabase config, browser token persistence, broad credential reveal, or `anon` CRM RPC execution.
5. Keep `ROLLBACK.md` and this file current whenever the architecture, privilege boundary, CI deployment policy, or recovery strategy materially changes.
