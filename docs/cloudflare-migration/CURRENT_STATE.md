# GrowthOps CRM Current State

Last reviewed: 2026-08-25

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

### Post-P5 rate-limit concurrency

Production migration `20260825075808 / post_p5_rate_limit_concurrency` serializes the reviewed login trusted-source/user bucket and per-workspace/user unlock/reveal rate-limit subjects with transaction-level advisory locks while preserving the existing thresholds and authentication order. Unlock/reveal rejected outcomes that require durable audit evidence use bounded safe JSON envelopes; both BFF implementations map only the reviewed envelopes to the established 400/429 contract and fail unknown envelopes closed. Detailed acceptance evidence is retained in `POST_P5_RATE_LIMIT_CONCURRENCY.md`.

## Current Supabase privilege state

The canonical repository gates encode the accepted post-P5 Production privilege shape:

- effective EXECUTE across all `public` functions for `anon / authenticated / service_role`: `0 / 0 / 12`;
- the 12 effective `service_role` functions are the reviewed CRM BFF/bootstrap entry allowlist;
- the historical `rls_auto_enable()` event-trigger helper is now postgres-only for direct EXECUTE, while the postgres-owned `ensure_rls` event trigger remains active and bound to it;
- direct service-role CRM table grants are removed;
- direct service-role CRM sequence grants are removed;
- postgres-created future objects in `public` no longer receive automatic `service_role` table, sequence, or function privileges;
- future non-`crm_*` functions/procedures created or altered in `public` are normalized fail-closed by `growthops_public_noncrm_function_acl_guard_ddl`, which removes direct/effective `PUBLIC`, `anon`, `authenticated`, and `service_role` EXECUTE exposure;
- the existing `growthops_crm_acl_guard_ddl` remains authoritative for the exact reviewed `crm_*` service-role function allowlist and denies broad relation/procedure exposure;
- RLS-alter guards cover the protected CRM table namespace;
- browser roles remain blocked from sensitive credential/Vault internals.

The future-object boundary was verified in Production with a transaction-contained DDL probe: a synthetic non-CRM function, table, and sequence all met the fail-closed target and were then rolled back; all three probe objects were confirmed absent afterward.

Do not restore `anon` RPC execution, broad service-role relation/function access, or permissive future-object defaults as a normal hosting rollback. Use the exact migration-specific rollback process in `ROLLBACK.md` only for a diagnosed database-control regression.

## Current Production database checkpoint

A fresh read-only Production inventory was revalidated on 2026-08-25 after the applied migration `20260825075808 / post_p5_rate_limit_concurrency`. The preceding accepted migration `20260825040850 / post_p5_public_default_privilege_guard` remains applied and authoritative for future-object default-deny behavior. Using the same deterministic catalog query retained in `supabase/baseline/p0_schema_security_fingerprint.sql`, the current CRM schema/security checkpoint is:

- inventory lines: `200`;
- SHA-256: `77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`;
- effective function EXECUTE boundary across all `public` functions for `anon / authenticated / service_role`: `0 / 0 / 12`;
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`;
- existing non-CRM public functions/procedures executable by `anon`, `authenticated`, or `service_role`: `0`;
- direct CRM table grants for those application roles: `0 / 0 / 0`;
- direct CRM sequence grants for those application roles: `0 / 0 / 0`;
- CRM RLS: enabled on `9 / 9` tables, with `0` browser-facing policies under the current RPC-only/default-deny design;
- ordinary workspace sensitive-key matches: `0`;
- server audit sensitive-payload-value matches: `0`.

The primary fingerprint changed from the preceding `200 / bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1` checkpoint because the rate-limit concurrency migration intentionally replaced three `crm_*` function definitions. The older hash remains historical evidence for its accepted phase.

Three repository-managed Post-P5 DDL guards live outside the primary fingerprint's historical `crm_*` function namespace. Current recovery comparison therefore also uses the read-only supplemental query in `supabase/baseline/post_p5_crm_guard_security_fingerprint.sql`, documented in `POST_P5_GUARD_FINGERPRINT.md`. Its accepted Production checkpoint is:

- guard inventory lines: `9`;
- guard SHA-256: `2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- scope: `growthops_crm_acl_guard_ddl`, `growthops_crm_rls_guard_ddl`, and `growthops_public_noncrm_function_acl_guard_ddl` function definitions/owners, application-role EXECUTE truth, and event-trigger event/enabled/tags/function bindings.

The supplemental guard checkpoint does not alter or replace the primary `200 / 77ba3a7c...` comparison contract. Refresh both checkpoints after a future schema/ACL/function/guard change that can affect their respective scopes.

This is the **current catalog/security comparison anchor**, not a replacement for a full database schema export. The historical P0 fingerprints remain valid evidence for their own phases, including the accepted `195 / edfcd23e...` relation-ACL checkpoint before later Post-P5 function/constraint changes. The outstanding full schema-only `pg_dump`/equivalent export remains a separate P0 recovery deliverable; do not claim full disaster-recovery schema portability from this fingerprint alone.

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

For the rate-limit concurrency runtime release, PR head `775bd321b8f09c36609da7e10afa274662582bc4` passed CRM Build Gate run #68, and merged `main@0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6` passed push-triggered run #69.

Subsequent recovery/documentation authority updates passed through `main@2f651a3baca51e8d1fdb1330d40432cdbbf19433` / run #75. Vercel Git deployment-policy hardening then passed slash-branch PR run #76 and merged-main run #77 at `main@91c0edcb24b79d282faa72d7d83435a1e1265d30`.

A change is not considered merge-safe merely because it is documentation-only or because one hosting platform deploys. The expected workflow remains: isolated branch → narrow diff → canonical gate → inspect final parity marker → merge with expected head SHA → verify resulting Production deployment.

## Hosting/deployment policy

### Vercel

`vercel.json` is default-deny for non-main Git deployments and enables Git deployment for `main` only. The current policy uses slash-safe minimatch globstar deny (`"**": false`) plus exact `"main": true`; the prior bare-star form allowed slash-containing branch names such as `docs/...` to fall through to Vercel's unspecified-branch default. Pull requests therefore rely on the secret-free GitHub canonical gate while merged `main` triggers Vercel Production.

The corrected policy was accepted by PR #86:

- slash-containing branch `ops/vercel-preview-globstar-20260825` produced no new normal Vercel Preview deployment during the acceptance observation;
- CRM Build Gate #76: completed / success;
- merged `main`: `91c0edcb24b79d282faa72d7d83435a1e1265d30`;
- merged-main CRM Build Gate #77: completed / success.

The stable Vercel application alias is:

`https://growthops-crm.vercel.app`

Current validated Vercel Production deployment:

- deployment: `dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6`;
- state: `READY`;
- Git commit: `91c0edcb24b79d282faa72d7d83435a1e1265d30`;
- stable alias assigned successfully.

The current Production homepage returned successfully, and unauthenticated `GET /api/crm` returned `405` with `METHOD_NOT_ALLOWED`, `Allow: POST`, no-store caching, and the expected security headers rather than executing an RPC. Recent Production runtime-error inspection found no new error cluster in the checked window.

For rollback, do not permanently pin an ancient pre-P5 build. Use a READY, gate-accepted `main` Production deployment compatible with the current database privilege/function state. See `ROLLBACK.md`.

Vercel Preview secret scope is **verified open**, not unverified. PR #85 Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` failed at `sh build.sh` with `PREVIEW_SECRET_BOUNDARY_FAILED` because a server secret was present without an explicit staging Supabase URL. No secret value was printed or recorded. PR #86 prevents the normal non-main Git Preview execution path, but platform cleanup remains required because the Preview-scoped secret itself has not been proven removed.

### Cloudflare Pages

The Cloudflare Pages project uses `main` as the Production branch and the same canonical build/output contract. `cloudflare_p1_verify.py` requires deterministic parity for the pinned production artifacts and also guards the inert top-level 404 and static security headers.

The last independently verified Cloudflare Production runtime-compatible deployment remains:

- deployment: `49a23f7f-5fbe-4894-9b8e-ad7b25005d70`;
- branch/commit: `main@0eefbe3`;
- state: `success`.

A later documentation-only Cloudflare Production deployment `5ddf431a-865a-4c88-9fc0-a948b908d1ec` for `main@5172508` was eventually marked `skipped` because a newer deployment had been queued before its build started. After the connected Opera browser became unavailable, the newer Cloudflare deployment ID/current Git SHA could not be independently reverified. Do not infer Cloudflare's latest Git SHA from GitHub or Vercel state. The last verified `0eefbe3` Cloudflare deployment remains runtime-compatible with the accepted Supabase concurrency migration.

Cloudflare Preview must not silently use Production Supabase. Standard Pages Preview hosts require an explicit isolated staging `GROWTHOPS_SUPABASE_URL` when a server secret is active; otherwise the runtime/build is expected to fail closed. Do not weaken the origin guard to make Preview pass.

Cloudflare Dashboard verification on 2026-08-25 showed that Preview still has a `GROWTHOPS_SUPABASE_SECRET_KEY` binding; no secret value is recorded here. With no explicit isolated staging URL, the repository guard rejects the Preview configuration as designed. Platform cleanup remains open: remove the Production secret from Preview or configure an explicitly isolated staging URL plus matching staging secret.

At this checkpoint the **runtime/database compatibility contract** is aligned: Supabase Production has the accepted concurrency migration, GitHub `main` and Vercel Production contain the compatible BFF/runtime, and the last independently verified Cloudflare Production also contains that compatible runtime. Exact Cloudflare deployment-SHA freshness after later documentation/config-only `main` commits remains unverified until the Cloudflare connection is available again.

## Security headers / static fail-closed behavior

The canonical gate verifies parity between Vercel security-header policy and Cloudflare output/function responses. Unknown top-level static paths use an inert, script-free 404 instead of an active SPA fallback that could expose CRM runtime material on unintended paths.

Current CSP still preserves the inline/runtime compatibility required by the existing shipped frontend. Tightening CSP further is a separate frontend/dependency project and must not be done by deleting required canonical build assets or weakening the output parity gate.

## Recovery authority

Operational rollback instructions are in:

`ROLLBACK.md`

The core rule is: **hosting rollback and database privilege rollback are separate operations**. Route back to a compatible validated Vercel server-boundary build first; change Supabase privileges only when a specific database security migration is proven to be the cause, and then only through its exact reviewed rollback artifact.

`P0_MIGRATION_LEDGER.md` preserves the remote migration history and repository mapping. Historical 2026-08-13/14 SQL gaps remain explicitly unresolved rather than reconstructed from guesses. Later forward migrations must remain mapped to genuine repository SQL, and the current Production catalog/security checkpoints above should be refreshed after any future schema/ACL/function change. The repository-backed `20260825075808 / post_p5_rate_limit_concurrency` mapping is recorded in `P0_MIGRATION_LEDGER_20260825_APPENDIX.md` and `POST_P5_RATE_LIMIT_CONCURRENCY.md` pending the next consolidated historical-ledger refresh.

## Historical phase documents

Use phase documents for detailed evidence:

- `P0_*.md`: recovery/fingerprint baseline and isolated restore proof;
- `P1_*.md`: initial Cloudflare static Pages parity/Preview acceptance;
- `P2A_CRM_BFF.md`: first `/api/crm` Cloudflare parity port;
- `P2B_SERVER_IDENTITY.md`: server-only Supabase identity, request IDs, log filtering and error sanitization;
- `P3P4_ATTACK_REGRESSION.md`: attack-style BFF regression and pre-P5 inventory;
- `P5_*.md`: incremental `anon` RPC revocation history;
- `POST_P5_*.md`: service-role minimization, relation ACL, trusted-source login buckets, ACL/RLS guards, future-object default-deny, later input/schema invariants, Preview secret boundary, and rate-limit concurrency hardening.

Those documents intentionally preserve the state observed at their own phase. Their historical fingerprints, grant counts, “next phase” sections, or Preview assumptions must not be interpreted as the current Production contract when they differ from this file or the canonical build gates.

## Current maintenance rules

1. Prefer small, single-purpose PRs with explicit rollback and no unrelated refactors.
2. Do not delete files solely because their names look historical; prove they are outside build, CI, runtime and documentation dependencies first.
3. Do not weaken fail-closed Preview/Production origin checks to accommodate platform configuration gaps.
4. Do not reintroduce browser Supabase config, browser token persistence, broad credential reveal, `anon` CRM RPC execution, or permissive future-object defaults in `public`.
5. Keep `ROLLBACK.md` and this file current whenever the architecture, privilege boundary, CI deployment policy, recovery strategy, or accepted hosting checkpoint materially changes.
6. Keep platform-secret scope claims evidence-based: Vercel and Cloudflare Preview cleanup are both currently confirmed outstanding, even though normal Vercel non-main Git Preview execution is now disabled.
