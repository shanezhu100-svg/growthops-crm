# GrowthOps CRM Current State

Last reviewed: 2026-08-30

This file is the **current-state authority** for the CRM hosting/security migration. Phase documents in this directory (P0, P1, P2-A, P2-B, P3/P4, P5, and Post-P5) are retained as implementation and acceptance evidence; when a phase document describes a future step that has since been completed, this file and the current canonical build gates take precedence. Database-specific checkpoint detail added on 2026-08-30 is also retained in `CURRENT_DATABASE_AUTHORITY_20260830.md`; that file is authoritative where an older recovery artifact is intentionally described at its historical 51-migration checkpoint.

## Current application boundary

The browser uses a same-origin CRM backend-for-frontend at `/api/crm` on both supported hosting paths:

- Vercel: `api/crm.js`;
- Cloudflare Pages Functions: `functions/api/crm.js`.

The browser does not receive or use a Supabase publishable URL/key configuration for direct CRM RPC access. Browser RPC traffic goes through the same-origin BFF.

Both BFFs require the server-only `GROWTHOPS_SUPABASE_SECRET_KEY` identity for allowlisted upstream RPC execution; there is no publishable-key fallback. Production Supabase origin selection is pinned to the canonical project and invalid/mismatched Production targets fail closed before upstream fetch. Both server implementations also enforce the accepted same-origin/session/input boundaries and a bounded 15-second upstream request timeout that converges through the existing sanitized generic 502 path.

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

Current input/resource guards include a 4 MiB API body limit, top-level object request envelope, UTF-8 byte bounds for login/admin/unlock passwords and user identity fields, a bounded session-token contract, exact Production Supabase-origin pinning, and a 15-second server-side upstream timeout. The canonical tests are authoritative for exact limits and failure semantics.

### Post-P5 rate-limit concurrency

Production migration `20260825075808 / post_p5_rate_limit_concurrency` serializes the reviewed login trusted-source/user bucket and per-workspace/user unlock/reveal rate-limit subjects with transaction-level advisory locks while preserving the existing thresholds and authentication order. Unlock/reveal rejected outcomes that require durable audit evidence use bounded safe JSON envelopes; both BFF implementations map only the reviewed envelopes to the established 400/429 contract and fail unknown envelopes closed. Detailed acceptance evidence is retained in `POST_P5_RATE_LIMIT_CONCURRENCY.md`.

The later reviewed migration `20260830071649 / client_account_safe_summary_correspondence` replaces only the server-side account safe-summary shape used for exact per-account correspondence. It does not write customer rows or broaden browser-role privileges.

## Current Supabase privilege state

The canonical repository gates encode the accepted post-P5 Production privilege shape:

- effective EXECUTE across all `public` functions for `anon / authenticated / service_role`: `0 / 0 / 12`;
- the 12 effective `service_role` functions are the reviewed CRM BFF/bootstrap entry allowlist;
- the historical `rls_auto_enable()` event-trigger helper is postgres-only for direct EXECUTE, while the postgres-owned `ensure_rls` event trigger remains active and bound to it;
- direct service-role CRM table grants are removed;
- direct service-role CRM sequence grants are removed;
- postgres-created future objects in `public` no longer receive automatic `service_role` table, sequence, or function privileges;
- future non-`crm_*` functions/procedures created or altered in `public` are normalized fail-closed by `growthops_public_noncrm_function_acl_guard_ddl`, which removes direct/effective `PUBLIC`, `anon`, `authenticated`, and `service_role` EXECUTE exposure;
- the existing `growthops_crm_acl_guard_ddl` remains authoritative for the exact reviewed `crm_*` service-role function allowlist and denies broad relation/procedure exposure;
- RLS-alter guards cover the protected CRM table namespace;
- browser roles remain blocked from sensitive credential/Vault internals.

The future-object boundary was verified with a transaction-contained DDL probe: synthetic non-CRM function/table/sequence objects met the fail-closed target and rolled back cleanly. The accepted **future-object default-privilege hardening** boundary remains `20260825040850 / post_p5_public_default_privilege_guard`.

Do not restore `anon` RPC execution, broad service-role relation/function access, or permissive future-object defaults as a normal hosting rollback. Use the exact migration-specific rollback process in `ROLLBACK.md` only for a diagnosed database-control regression.

## Current Production database checkpoint

The current Production database authority was refreshed after the reviewed account-correspondence migration on 2026-08-30:

- migration rows: `52`;
- migration head: `20260830071649 / client_account_safe_summary_correspondence`;
- primary fingerprint: `200 / 8ff7dd1447bf2cea9802438f91e8e1d3bf34bc7f7b4878592dd2eca8b06da7f9`;
- three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`;
- wider-public fingerprint: `225 / b89328f5548d4787a650b7f079bc1843125cc7c1b550d959a8cb4df2b2df04f2`;
- effective CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`;
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`;
- direct CRM table and sequence application-role grants remain absent;
- CRM RLS remains enabled on `9 / 9` business tables under the current RPC-only/default-deny design.

`CURRENT_DATABASE_AUTHORITY_20260830.md` is the database-specific source for this 52-migration checkpoint and its exact recovery-forward procedure. The immediately preceding 51-migration `200 / 77ba3a7c...`, guard `9 / 2a6c96fe...`, wider-public `225 / a0078c5d...` state remains historical Recovery Bundle v3 acceptance evidence and must not be rewritten as if the old artifact contained the later migration.

The three repository-managed GrowthOps DDL guards remain `growthops_crm_acl_guard_ddl`, `growthops_crm_rls_guard_ddl`, and `growthops_public_noncrm_function_acl_guard_ddl`. The accepted hosted state also retains the postgres-owned `ensure_rls` event trigger. Fingerprint drift is an investigation trigger, not automatic repair authorization.

## Current credential/storage boundary

- customer password/2FA secret values remain in Supabase Vault-backed server-side handling;
- browser credential reveal uses `crm_reveal_client_secret_value_v5` single-value transport only;
- broad v3/v4/full reveal is blocked from the browser path;
- revealed scalar values are ephemeral in memory and are cleared on the accepted timeout/background/navigation behavior;
- workspace state has a hard secret-material guard;
- normal CRM backups must not include customer password/2FA values;
- customer secrets must not be copied to Pages, Workers KV, D1, R2, logs, GitHub, or ordinary backups.

## Current frontend/runtime boundary

The browser frontend no longer relies on third-party runtime CDN execution for the reviewed application dependencies:

- Tailwind Play is removed; Tailwind 3.4.17 is compiled at build time to same-origin `/tailwind.css` with pinned standalone-CLI digests;
- Vue 3.5.41 and XLSX 0.18.5 are downloaded only at build time from exact versioned sources, redirect-denied, SHA-256 verified, and emitted as same-origin vendor assets;
- Font Awesome 6.5.2 and Inter font assets are similarly pinned and emitted same-origin;
- application-owned inline scripts and style blocks are extracted to same-origin static assets;
- literal/bound style attributes and first-party CSSOM style sinks were migrated to static class/data-attribute/progress-value behavior;
- Vue now ships the `vue-3.5.41.runtime.global.js` runtime-only build plus a deterministic, hash-pinned precompiled render registry; the old compiler-inclusive `vue-3.5.41.global.js` is explicitly forbidden by the final artifact verifier;
- the render registry restores only the reviewed Vue 3.5.41 runtime-compiled public-instance proxy semantics required by precompiled `with (_ctx)` render factories, without shipping a compiler or dynamic code generation;
- real Chromium CI proves the final app mounts (`v-cloak` clears) and the client-form credential DOM regression remains correct.

Current CSP is same-origin/eval-free for scripts: `script-src 'self'`; `unsafe-eval` and `unsafe-inline` are absent. Style attributes are denied, application resource references are same-origin, and the final Vercel/Cloudflare header policies are generated from one authority and checked for parity. The canonical final artifact verifier pins 28 Production artifacts and explicitly fails if the old Vue compiler asset returns.

## Current build and merge authority

The canonical local/CI build is:

`sh build.sh && python3 cloudflare_p1_verify.py`

The required GitHub build additionally repeats `test_vue_runtime_only_output.py` and runs the real Chromium mount and client-form credential regression against the exact final `dist` before final Cloudflare parity verification.

GitHub Actions provides the canonical PR build/security gate and runs without CRM/Supabase secrets. Its current quota/security contract includes:

- `contents: read` token permissions;
- checkout credentials not persisted;
- all external GitHub Action dependencies use immutable 40-hex commit SHAs;
- recovery workflows are manual-only, protected-main-only, project-ref-confirmed, one-secret, bounded-time jobs;
- recovery workflows prohibit nondeterministic `version: latest` and pin the accepted Supabase CLI `2.116.0`;
- Ubuntu 24.04 and Node 24 for the canonical CRM build runner;
- no CRM/Supabase secrets in the PR runner;
- complete canonical CRM build/security/business-semantic regression suite;
- final Cloudflare artifact/output parity verification.

GitHub `main` protection was accepted on 2026-08-27. The live branch resource reported `protected=true`, required status-check enforcement `everyone`, and required context `build` (GitHub Actions app_id 15368). Dashboard acceptance also confirmed PR-before-merge, up-to-date required checks, no ordinary bypass, and force-push/deletion disabled. Issue #91: closed / completed. The expected release path remains: isolated branch → green required `build` Gate → expected-head merge → merged-main verification.

Recovery Bundle v3, workflow supply-chain hardening, dependency self-hosting, CSP hardening, and the Vue runtime-only cutover all followed this protected path. PR #178 passed both the required `build` and Cloudflare Preview before squash merge; merged `main@c309f62530552adaef8dec4715f8d0faf04d19df` then passed both merged-main `build` and Cloudflare main checks.

A change is not considered merge-safe merely because it is documentation-only or because one hosting platform deploys. The expected workflow remains: isolated branch → narrow diff → canonical gate → inspect final parity marker → merge with expected head SHA → verify resulting Production deployment.

## Hosting/deployment policy

### Vercel

`vercel.json` is default-deny for non-main Git deployments and enables Git deployment for `main` only. The current policy uses slash-safe minimatch globstar deny (`"**": false`) plus exact `"main": true`; the prior bare-star form allowed slash-containing branch names such as `docs/...` to fall through to Vercel's unspecified-branch default. Pull requests therefore rely on the secret-free GitHub canonical gate while merged `main` triggers Vercel Production. Clearly non-runtime main changes may be conservatively ignored by the reviewed `vercel-ignore-build.sh`; unknown/runtime/config changes continue to build.

The stable Vercel application alias is:

`https://growthops-crm.vercel.app`

Current runtime/security deployment checkpoint after the Vue runtime-only cutover:

- deployment: `dpl_8qVjdUsKiWayM3jg987rV8H8Pu6e`;
- state: `READY`;
- Git commit: `c309f62530552adaef8dec4715f8d0faf04d19df`;
- merged-main required `build`: completed / success;
- Vercel error/fatal runtime logs for the post-merge checkpoint: none found in the reviewed two-hour window.

The older deployment `dpl_JWXVvjCdjRF59gMrZycDUJEXYP7G` remains historical functional POST evidence from the Production-server-secret repair: its logs showed successful `POST /api/crm` 200 responses and the expected unauthenticated/session-required 401 boundary. It no longer represents the latest frontend/runtime artifact set.

For rollback, do not permanently pin an ancient pre-P5 build. Use a READY, gate-accepted `main` Production deployment compatible with the current database privilege/function state. See `ROLLBACK.md`.

Historical fail-closed evidence is retained: on 2026-08-25 Vercel Preview secret scope was **verified open**, and PR #85 Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` failed at `sh build.sh` with `PREVIEW_SECRET_BOUNDARY_FAILED` because a server secret was present without an explicit staging Supabase URL. No secret value was printed or recorded. PR #86 then prevented the normal non-main Git Preview execution path.

**Preview Production-secret cleanup accepted on 2026-08-27.** Independent Vercel CLI verification showed `Vercel Preview: no project environment variables`, while Production retained hidden `GROWTHOPS_SUPABASE_SECRET_KEY` scoped to Production only. The Production-only value was restored to a valid Supabase server identity and runtime was successfully revalidated. Issue #92: closed / completed.

### Cloudflare Pages

Cloudflare Pages uses `main` as the Production branch and the same canonical build/output contract. `cloudflare_p1_verify.py` now requires deterministic parity for 28 pinned Production artifacts, explicitly forbids the retired compiler-inclusive Vue asset, and also guards the inert top-level 404 plus static security headers.

For `main@c309f62530552adaef8dec4715f8d0faf04d19df`, the Cloudflare Pages main check completed successfully after PR #178 merged. This supersedes the old “latest independently verified Cloudflare runtime-compatible deployment is `main@0eefbe3`” freshness statement. Historical deployment IDs and phase evidence remain valid for their own checkpoints but are no longer the current hosting-freshness authority.

Cloudflare Preview must not silently use Production Supabase. Standard Pages Preview hosts require an explicit isolated staging `GROWTHOPS_SUPABASE_URL` when a server secret is active; otherwise the runtime/build is expected to fail closed. Do not weaken the origin guard to make Preview pass.

Historical Dashboard evidence from 2026-08-25 showed a Preview `GROWTHOPS_SUPABASE_SECRET_KEY` binding without an accepted isolated staging URL; the repository guard correctly rejected that configuration. On 2026-08-27 the binding was deleted and the Preview environment was rechecked empty. **Preview Production-secret cleanup accepted on 2026-08-27:** `Cloudflare Preview: `GROWTHOPS_SUPABASE_SECRET_KEY` removed`; Cloudflare Production retains its encrypted Production binding. Issue #92: closed / completed.

At this checkpoint the runtime/database compatibility contract is aligned: the protected `main` runtime uses the current same-origin BFF/security boundary; Production database authority is 52 migrations; and the latest Vercel plus Cloudflare main evidence is aligned to the accepted runtime-only frontend cutover.

## Security headers / static fail-closed behavior

The canonical gate verifies parity between Vercel security-header policy and Cloudflare static/function responses. Unknown top-level static paths use an inert, script-free 404 instead of an active SPA fallback that could expose CRM runtime material on unintended paths.

Current script CSP is `script-src 'self'` with `unsafe-eval` and `unsafe-inline` absent. The browser no longer needs Tailwind Play or the Vue compiler. `script-src-attr` and `style-src-attr` are denied; `connect-src` remains same-origin only; image/media remain self/data/blob; COOP/CORP are same-origin; robots are noindex/nofollow/noarchive. Do not relax these controls merely to simplify a future frontend dependency change.

## Recovery authority

Operational rollback instructions are in:

`ROLLBACK.md`

The core rule is: **hosting rollback and database privilege rollback are separate operations**. Route back to a compatible validated server-boundary build first; change Supabase privileges only when a specific database security migration is proven to be the cause, and then only through its exact reviewed rollback artifact.

`P0_MIGRATION_LEDGER.md` is now the consolidated current remote migration-history and repository-mapping authority through `20260830071649 / client_account_safe_summary_correspondence`. Historical 2026-08-13/14 SQL gaps remain explicitly unresolved rather than reconstructed from guesses. `P0_MIGRATION_LEDGER_20260825_APPENDIX.md` is retained as point-in-time acceptance evidence, not as a required second source for determining the current migration head. Later forward migrations must continue to map to genuine repository SQL, and the current Production fingerprints must be refreshed when a reviewed schema/ACL/function/guard/extension change affects their respective scopes.

Recovery Bundle v3 remains the accepted zero-to-51 portable recovery base. Its accepted artifact came from workflow run `33079493119`; its original fresh-hosted restore, three 51-migration fingerprints, future-object probe, synthetic cloud acceptance and rollback-clean proof remain historical truth. It must not be described as if it already contained migration 52.

Until a newer recovery bundle is independently generated and accepted, recovery to current Production is:

1. restore accepted Recovery Bundle v3 in the documented order `schema.sql` → `event-triggers.sql` → `post-schema-security.sql` → `migration-ledger.sql`;
2. apply repository migration `supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql`;
3. verify `52 / 20260830071649` and current primary `200 / 8ff7dd1447...`, guard `9 / 2a6c96fe...`, wider-public `225 / b89328f5...`;
4. preserve `0 / 0 / 12`, RLS/default-deny/event-trigger invariants;
5. run the existing transaction-contained synthetic recovery acceptance only on a disposable target and prove rollback-clean state.

Issue #93 remains closed / completed because the accepted Bundle v3 recovery exercise itself is complete; the later repository-backed forward migration is covered by the current database authority rather than retroactively altering the historical artifact.

## Historical phase documents

Use phase documents for detailed evidence:

- `P0_*.md`: recovery/fingerprint baseline and isolated restore proof;
- `P1_*.md`: initial Cloudflare static Pages parity/Preview acceptance;
- `P2A_CRM_BFF.md`: first `/api/crm` Cloudflare parity port;
- `P2B_SERVER_IDENTITY.md`: server-only Supabase identity, request IDs, log filtering and error sanitization;
- `P3P4_ATTACK_REGRESSION.md`: attack-style BFF regression and pre-P5 inventory;
- `P5_*.md`: incremental `anon` RPC revocation history;
- `POST_P5_*.md`: service-role minimization, relation ACL, trusted-source login buckets, ACL/RLS guards, future-object default-deny, later input/schema invariants, Preview secret boundary, and rate-limit concurrency hardening.

Those documents intentionally preserve the state observed at their own phase. Their historical fingerprints, grant counts, “next phase” sections, or Preview assumptions must not be interpreted as the current Production contract when they differ from this file, `CURRENT_DATABASE_AUTHORITY_20260830.md`, or the canonical build gates.

## Current maintenance rules

1. Prefer small, single-purpose PRs with explicit rollback and no unrelated refactors.
2. Do not delete files solely because their names look historical; prove they are outside build, CI, runtime and documentation dependencies first. A 2026-08-30 attempted cleanup of `test_vue_runtime_final_stage_probe.py` was correctly rejected by the full Gate because `test_style_attr_cssom_output.py` still imports it as a pre-cutover template authority.
3. Do not weaken fail-closed Preview/Production origin checks even though the Production secret has now been removed from Preview scopes.
4. Do not reintroduce browser Supabase config, browser token persistence, broad credential reveal, `anon` CRM RPC execution, permissive future-object defaults in `public`, external browser script CDNs, the Vue browser compiler, or dynamic-eval CSP allowances.
5. Keep `ROLLBACK.md`, `CURRENT_DATABASE_AUTHORITY_20260830.md`, and this file current whenever the architecture, privilege boundary, CI deployment policy, recovery strategy, or accepted hosting checkpoint materially changes.
6. Keep platform-secret scope claims evidence-based: Vercel and Cloudflare Preview Production-secret cleanup were independently accepted on 2026-08-27; historical fail-closed evidence remains retained for audit history.
7. Issues #91, #92, #93 and #95 are closed / completed. Recovery-target keep/pause/delete is an optional lifecycle choice and must not be inferred from technical acceptance closure.
