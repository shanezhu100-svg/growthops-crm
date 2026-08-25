# GrowthOps CRM Current State

Last reviewed: 2026-08-25

This file is the **current-state authority** for the CRM hosting/security migration. Phase documents in this directory (P0, P1, P2-A, P2-B, P3/P4, P5, and Post-P5) are retained as implementation and acceptance evidence; when a phase document describes a future step or historical checkpoint that has since changed, this file and the current canonical build gates take precedence.

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

### Post-P5 concurrency hardening

Production migration `20260825075808 / post_p5_rate_limit_concurrency` serializes security-sensitive rate-limit subjects using transaction-level PostgreSQL advisory locks while preserving the existing thresholds and authentication ordering:

- login trusted-source/user bucket: namespace `90813011`;
- credential unlock per workspace/user: namespace `90813012`;
- credential reveal per workspace/user: namespace `90813013`.

Unlock/reveal rejected outcomes that must leave durable audit evidence use bounded safe JSON envelopes so the database transaction can commit. The Vercel and Cloudflare BFFs translate only the reviewed envelopes to the existing HTTP 400/429 contract and fail unknown envelopes as an upstream-contract error. Detailed acceptance evidence is in `POST_P5_RATE_LIMIT_CONCURRENCY.md`.

## Current Supabase privilege state

The canonical repository gates encode the accepted post-P5 Production privilege shape:

- effective EXECUTE across all `public` functions for `anon / authenticated / service_role`: `0 / 0 / 12`;
- the 12 effective `service_role` functions are the reviewed CRM BFF/bootstrap entry allowlist;
- there are currently 40 `crm_*` functions in the reviewed inventory;
- the historical `rls_auto_enable()` event-trigger helper is postgres-only for direct EXECUTE, while the postgres-owned `ensure_rls` event trigger remains active and bound to it;
- direct service-role CRM table grants are removed;
- direct service-role CRM sequence grants are removed;
- postgres-created future objects in `public` no longer receive automatic `service_role` table, sequence, or function privileges;
- future non-`crm_*` functions/procedures created or altered in `public` are normalized fail-closed by `growthops_public_noncrm_function_acl_guard_ddl`, which removes direct/effective `PUBLIC`, `anon`, `authenticated`, and `service_role` EXECUTE exposure;
- the existing `growthops_crm_acl_guard_ddl` remains authoritative for the exact reviewed `crm_*` service-role function allowlist and denies broad relation/procedure exposure;
- RLS-alter guards cover the protected CRM table namespace;
- browser roles remain blocked from sensitive credential/Vault internals.

The future-object boundary was previously verified in Production with a transaction-contained DDL probe: a synthetic non-CRM function, table, and sequence all met the fail-closed target and were then rolled back; all three probe objects were confirmed absent afterward.

Do not restore `anon` RPC execution, broad service-role relation/function access, or permissive future-object defaults as a normal hosting rollback. Use the exact migration-specific rollback process in `ROLLBACK.md` only for a diagnosed database-control regression.

## Current Production database checkpoint

A fresh read-only Production inventory was revalidated on 2026-08-25 after the applied migration `20260825075808 / post_p5_rate_limit_concurrency`. Using the deterministic catalog query retained in `supabase/baseline/p0_schema_security_fingerprint.sql`, the current CRM schema/security checkpoint is:

- inventory lines: `200`;
- SHA-256: `77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- effective function EXECUTE for `anon / authenticated / service_role`: `0 / 0 / 12`;
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`;
- existing non-CRM public functions/procedures executable by `anon`, `authenticated`, or `service_role`: `0`;
- direct CRM table grants for those application roles: `0 / 0 / 0`;
- direct CRM sequence grants for those application roles: `0 / 0 / 0`;
- CRM RLS: enabled on `9 / 9` tables, with `0` browser-facing policies under the current RPC-only/default-deny design;
- ordinary workspace sensitive-key matches: `0` at the latest accepted security checkpoint;
- server audit sensitive-payload-value matches: `0` at the latest accepted security checkpoint.

The primary hash changed from the preceding `200 / bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1` checkpoint because the concurrency migration intentionally replaced three `crm_*` function definitions. The older hash remains historical evidence only.

Three repository-managed Post-P5 DDL guards live outside the primary fingerprint's historical `crm_*` function namespace. Current recovery comparison therefore also uses the read-only supplemental query in `supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`, documented in `POST_P5_GUARD_FINGERPRINT.md`. Its accepted Production checkpoint remains:

- guard inventory lines: `9`;
- guard SHA-256: `2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- scope: `growthops_crm_acl_guard_ddl`, `growthops_crm_rls_guard_ddl`, and `growthops_public_noncrm_function_acl_guard_ddl` function definitions/owners, application-role EXECUTE truth, and event-trigger event/enabled/tags/function bindings.

The supplemental guard checkpoint does not alter or replace the primary `200 / 77ba3a7c...` comparison contract. Refresh both checkpoints after a future schema/ACL/function/guard change that can affect their respective scopes.

This is the **current catalog/security comparison anchor**, not a replacement for a full database schema export. Historical P0 fingerprints remain valid evidence for their own phases. The outstanding full schema-only `pg_dump`/equivalent export remains a separate P0 recovery deliverable; do not claim full disaster-recovery schema portability from this fingerprint alone.

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

GitHub Actions is the hard merge gate and runs without CRM/Supabase secrets. Its current quota/security contract includes:

- `contents: read` token permissions;
- checkout credentials not persisted;
- SHA-pinned GitHub Actions;
- Node 24;
- no CRM/Supabase secrets in the runner;
- complete canonical CRM build/security regression suite;
- final Cloudflare artifact/output parity verification.

For the rate-limit concurrency release, PR head `775bd321b8f09c36609da7e10afa274662582bc4` passed CRM Build Gate run #68, and the resulting merged `main` commit `0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6` passed push-triggered run #69.

A change is not considered merge-safe merely because it is documentation-only or because one hosting platform deploys. The expected workflow remains: isolated branch → narrow diff → canonical gate → inspect final parity marker → merge with expected head SHA → verify resulting Production deployment.

## Hosting/deployment policy and accepted Production checkpoint

### Vercel

`vercel.json` is default-deny for non-main Git deployments and enables Git deployment for `main` only. This protects Hobby deployment quota. Pull requests rely on the secret-free GitHub canonical gate; merged `main` triggers Vercel Production.

Current accepted rate-limit concurrency Production deployment:

- deployment: `dpl_FNtV2oBQWPYZrm8BaShVybUm57fF`;
- Git commit: `0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6`;
- state: `READY`;
- stable alias: `https://growthops-crm.vercel.app`.

For rollback, do not permanently pin an ancient pre-P5 build. Use a READY, gate-accepted `main` Production deployment compatible with the current database privilege/function state. See `ROLLBACK.md`.

### Cloudflare Pages

The Cloudflare Pages project uses `main` as the Production branch and the same canonical build/output contract. `cloudflare_p1_verify.py` requires deterministic parity for the pinned production artifacts and also guards the inert top-level 404 and static security headers.

Current accepted rate-limit concurrency Production deployment:

- deployment: `49a23f7f-5fbe-4894-9b8e-ad7b25005d70`;
- branch/commit: `main@0eefbe3`;
- state: `success`;
- observed build duration: 46 seconds.

At this checkpoint Supabase Production, GitHub `main`, Vercel Production, and Cloudflare Pages Production are aligned on the accepted concurrency release.

## Preview secret boundary

Preview environments must not silently use Production Supabase. Standard Preview hosts require an explicit isolated staging `GROWTHOPS_SUPABASE_URL` when a server secret is active; otherwise the runtime/build is expected to fail closed. Do not weaken the origin guard to make Preview pass.

Platform verification on 2026-08-25 established:

- Cloudflare Preview still has a `GROWTHOPS_SUPABASE_SECRET_KEY` binding. No secret value is recorded in repository documentation. With no explicit isolated staging URL, the repository guard rejects the Preview configuration as designed. Cloudflare platform cleanup remains open: either remove the Production secret from Preview or configure an isolated staging URL plus matching staging secret.
- Vercel Production is verified, but Vercel Preview environment-variable scope could not be independently inspected through the available connected interface and browser session. Treat Vercel Preview secret isolation as **unverified**, not accepted or assumed clean.

`POST_P5_PREVIEW_SECRET_BOUNDARY.md` remains the detailed policy source, and `POST_P5_RATE_LIMIT_CONCURRENCY.md` records the current operational observation.

## Security headers / static fail-closed behavior

The canonical gate verifies parity between Vercel security-header policy and Cloudflare output/function responses. Unknown top-level static paths use an inert, script-free 404 instead of an active SPA fallback that could expose CRM runtime material on unintended paths.

Current CSP still preserves the inline/runtime compatibility required by the existing shipped frontend. Tightening CSP further is a separate frontend/dependency project and must not be done by deleting required canonical build assets or weakening the output parity gate.

## Recovery authority

Operational rollback instructions are in `ROLLBACK.md`.

The core rule is: **hosting rollback and database privilege/function rollback are separate operations**. Route back to a compatible validated Vercel server-boundary build first; change Supabase only when a specific database migration is proven to be the cause, and then only through its exact reviewed rollback artifact.

`P0_MIGRATION_LEDGER.md` preserves the historical remote migration history and repository mapping through its own review checkpoint. The later `20260825075808 / post_p5_rate_limit_concurrency` forward migration is repository-backed and is explicitly mapped in `POST_P5_RATE_LIMIT_CONCURRENCY.md`; it must be included when the consolidated ledger is next refreshed. Historical 2026-08-13/14 SQL gaps remain explicitly unresolved rather than reconstructed from guesses.

## Historical phase documents

Use phase documents for detailed evidence:

- `P0_*.md`: recovery/fingerprint baseline and isolated restore proof;
- `P1_*.md`: initial Cloudflare static Pages parity/Preview acceptance;
- `P2A_CRM_BFF.md`: first `/api/crm` Cloudflare parity port;
- `P2B_SERVER_IDENTITY.md`: server-only Supabase identity, request IDs, log filtering and error sanitization;
- `P3P4_ATTACK_REGRESSION.md`: attack-style BFF regression and pre-P5 inventory;
- `P5_*.md`: incremental `anon` RPC revocation history;
- `POST_P5_*.md`: service-role minimization, relation ACL, trusted-source login buckets, ACL/RLS guards, future-object default-deny, input/schema invariants, Preview secret boundary, and rate-limit concurrency hardening.

Those documents intentionally preserve the state observed at their own phase. Their historical fingerprints, grant counts, “next phase” sections, or Preview assumptions must not be interpreted as the current Production contract when they differ from this file or the canonical build gates.

## Current maintenance rules

1. Prefer small, single-purpose PRs with explicit rollback and no unrelated refactors.
2. Do not delete files solely because their names look historical; prove they are outside build, CI, runtime and documentation dependencies first.
3. Do not weaken fail-closed Preview/Production origin checks to accommodate platform configuration gaps.
4. Do not reintroduce browser Supabase config, browser token persistence, broad credential reveal, `anon` CRM RPC execution, or permissive future-object defaults in `public`.
5. Keep `ROLLBACK.md` and this file current whenever the architecture, privilege/function boundary, CI deployment policy, recovery strategy, or accepted Production database fingerprint materially changes.
6. Keep platform-secret scope claims evidence-based: an unverified environment is not equivalent to a clean environment.
