# GrowthOps CRM Current State

Last reviewed: 2026-08-30

This file is the **current-state authority** for the CRM hosting/security/runtime migration. Historical phase documents in this directory remain implementation and acceptance evidence for their own checkpoints; when older text conflicts with this file, `CURRENT_DATABASE_AUTHORITY_20260830.md`, or the canonical build gates, the newer authority takes precedence.

## Current application boundary

The browser uses a same-origin backend-for-frontend at `/api/crm` on both supported hosting paths:

- Vercel: `api/crm.js`
- Cloudflare Pages Functions: `functions/api/crm.js`

The browser does not receive a Supabase publishable URL/key for direct CRM RPC traffic. Both BFFs require server-only `GROWTHOPS_SUPABASE_SECRET_KEY`, enforce the exact reviewed RPC surface, same-origin/session/input boundaries, canonical Production Supabase-origin pinning, and a 15-second upstream timeout that converges through the existing sanitized generic 502 path. Invalid/mismatched Production targets fail closed before upstream fetch.

## Session and request boundary

Current enforced behavior includes POST-only action execution, same-origin CSRF/origin checks, exact RPC allowlisting, a `__Host-growthops_crm` HttpOnly/Secure/SameSite=Strict session cookie, server-side session-token authority, forged-body-token replacement, logout cookie clearing even on upstream failure, bounded request IDs, sanitized upstream errors, single-scalar credential reveal, 4 MiB request-body limits, object-only request envelopes, UTF-8 byte limits for reviewed password/user-identity fields, and bounded session tokens.

Credential unlock/reveal remains session/user/workspace bound with the accepted reauthentication and rate-limit behavior. Migration `20260825075808 / post_p5_rate_limit_concurrency` remains authoritative for concurrency serialization of reviewed login/unlock/reveal rate-limit subjects. The later `20260830071649 / client_account_safe_summary_correspondence` migration changes only the server-side per-account safe-summary shape used for exact Facebook/TikTok/Google/Instagram correspondence; it does not write customer rows or broaden browser-role privileges.

## Current Supabase privilege state

The accepted Production privilege boundary remains:

- effective EXECUTE across all `public` functions for `anon / authenticated / service_role`: `0 / 0 / 12`
- direct application-role CRM table grants: absent
- direct application-role CRM sequence grants: absent
- CRM RLS: enabled on `9 / 9` business tables under the RPC-only/default-deny design
- postgres/public future default `service_role` grants for tables / sequences / functions: `0 / 0 / 0`
- browser roles remain blocked from sensitive credential/Vault internals
- `rls_auto_enable()` is postgres-only for direct EXECUTE while postgres-owned `ensure_rls` remains active
- `growthops_crm_acl_guard_ddl`, `growthops_crm_rls_guard_ddl`, and `growthops_public_noncrm_function_acl_guard_ddl` remain the reviewed GrowthOps DDL guards

The accepted **future-object default-privilege hardening** boundary remains `20260825040850 / post_p5_public_default_privilege_guard`. Transaction-contained DDL probes have verified the fail-closed behavior and rollback-clean absence of synthetic probe objects.

Do not restore `anon` CRM RPC execution, broad service-role relation/function access, browser Supabase transport, or permissive future-object defaults as an ordinary hosting rollback.

## Current Production database checkpoint

`CURRENT_DATABASE_AUTHORITY_20260830.md` is the database-specific authority for the current hosted state:

- migration rows: `52`
- migration head: `20260830071649 / client_account_safe_summary_correspondence`
- primary fingerprint: `200 / 8ff7dd1447bf2cea9802438f91e8e1d3bf34bc7f7b4878592dd2eca8b06da7f9`
- three-guard fingerprint: `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`
- wider-public fingerprint: `225 / b89328f5548d4787a650b7f079bc1843125cc7c1b550d959a8cb4df2b2df04f2`
- effective CRM function EXECUTE `anon / authenticated / service_role`: `0 / 0 / 12`

The immediately preceding 51-migration checkpoint remains historical Recovery Bundle v3 evidence: primary `200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`, guard `9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`, wider-public `225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab`. It must not be rewritten as though the accepted v3 artifact already contained migration 52.

`P0_MIGRATION_LEDGER.md` is now the consolidated current remote migration-history and repository-mapping authority through `20260830071649 / client_account_safe_summary_correspondence`. Historical 2026-08-13/14 SQL gaps remain explicitly unresolved rather than reconstructed from guesses. `P0_MIGRATION_LEDGER_20260825_APPENDIX.md` remains point-in-time acceptance evidence and is not a second current migration-head authority.

## Recovery authority

Recovery Bundle v3 from workflow run `33079493119` remains the accepted zero-to-51 portable recovery base. Its fresh hosted restore, 51-entry migration ledger, three accepted historical fingerprints, future-object probe, synthetic cloud acceptance, and rollback-clean proof remain valid historical truth. Issue #93 remains closed / completed.

Until a newer bundle is independently generated and accepted, recovery to current Production is:

1. restore accepted Bundle v3 in order `schema.sql` → `event-triggers.sql` → `post-schema-security.sql` → `migration-ledger.sql`;
2. apply `supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql`;
3. verify `52 / 20260830071649` plus current primary/guard/wider-public fingerprints;
4. preserve `0 / 0 / 12`, RLS/default-deny/event-trigger invariants;
5. run the existing transaction-contained synthetic recovery acceptance only on a disposable target and prove rollback-clean state.

Hosting rollback and database privilege rollback are separate operations. Use `ROLLBACK.md` and exact reviewed rollback artifacts; fingerprint drift is an investigation trigger, not automatic repair authorization.

## Credential/storage and account-correspondence boundary

Customer password/2FA secret values remain in Supabase Vault-backed server handling. Browser reveal is v5 single-value only; broad v3/v4/full reveal is blocked from the browser path. Revealed scalar values are ephemeral in memory and cleared on accepted timeout/background/navigation behavior. Workspace state has a hard secret-material guard, and normal backups must not contain customer password/2FA values.

The 2026-08-30 account-correspondence/client-form fixes are now part of the accepted runtime:

- safe summaries preserve exact account identity across multiple Facebook/TikTok/etc. accounts;
- editing/refetching a client does not collapse saved credential status onto the wrong account;
- real Chromium regression covers multi-account refresh correspondence;
- saved login account values render as normal field text in the edit form while password material remains behind the reviewed masked/reveal boundary;
- focused Chromium credential regressions continue to prove no unexpected reveal RPC occurs during ordinary form display/edit interactions.

## Current frontend/runtime boundary

The browser no longer depends on third-party runtime CDN execution for reviewed application dependencies:

- Tailwind Play is removed; Tailwind 3.4.17 is compiled to same-origin `/tailwind.css` using pinned standalone-CLI digests;
- Vue 3.5.41, XLSX 0.18.5, Font Awesome 6.5.2, and Inter assets are exact-version/hash verified at build time and emitted same-origin;
- application-owned inline JS/CSS has been extracted to same-origin assets;
- literal/bound style attributes and reviewed CSSOM sinks were migrated to static classes/data/progress behavior;
- Vue ships the compiler-free `vue-3.5.41.runtime.global.js` plus a deterministic hash-pinned precompiled render registry;
- the retired compiler-inclusive `vue-3.5.41.global.js` is explicitly forbidden by the final verifier;
- the render registry restores only reviewed Vue runtime-compiled public-instance proxy semantics, without browser compiler or dynamic code generation.

Current CSP is same-origin and eval-free for scripts: `script-src 'self'`; `unsafe-eval` and `unsafe-inline` are absent. `script-src-attr` and `style-src-attr` are denied; `connect-src` is same-origin only; image/media are self/data/blob; COOP/CORP are same-origin; robots are noindex/nofollow/noarchive. Vercel and Cloudflare static/function security headers are generated from one authority and checked for exact parity.

The final Cloudflare artifact verifier pins 28 Production artifacts, including app JS/CSS, Tailwind, Vue runtime/render registry, XLSX, Font Awesome and Inter assets, and fails closed if the Vue compiler returns.

## Current finance/business boundary

The 2026-08-30 confirmed-profit correction is accepted in the final runtime. In ALL-client scope, current/confirmed actual net profit deducts only company project/public costs; costs already owned by a specific client are not deducted a second time at the aggregate layer. Selected-client profitability continues to deduct that client's costs. Expected net profit behavior is unchanged. The ACTUAL breakdown uses the same corrected cost basis, and future company month snapshots use total cost minus direct client cost while client snapshots retain their client cost basis.

Focused executable regression reproduces the reviewed `CNY 12,000` income / `CNY 2,520` client-owned cost case. The same required build also runs the wider advertising, finance period/rebate/amount/unique/settlement/client-status/receivable/visible-profit/cost-visibility/profit-confirmation/reconciliation, client module-home, assets credential-context and analytics business semantics suite.

## Current build and merge authority

The canonical portable build is:

`sh build.sh && python3 cloudflare_p1_verify.py`

The required GitHub `build` job additionally runs the real Chromium mount, client credential form, and multi-account refresh regressions against final `dist` before final parity verification. Current CI controls include Ubuntu 24.04, Node 24, `contents: read`, non-persisted checkout credentials, immutable 40-hex action SHAs, no CRM/Supabase secrets in the normal PR runner, and manual/protected-main/project-ref-confirmed recovery workflows.

GitHub `main` remains protected with required status context `build`. The expected release path remains isolated branch → green required `build` → expected-head merge → merged-main verification. A docs-only or single-platform-success change is not considered merge-safe by itself.

## Current hosting checkpoint

### Vercel

`vercel.json` remains default-deny for non-main Git deployment (`"**": false`, exact `"main": true`). Clearly non-runtime main changes may be conservatively skipped by `vercel-ignore-build.sh`; runtime/config/unknown changes continue to build.

Latest accepted runtime/business Production after PR #183:

- Git commit: `23f3bbd7e491357d2533a2c5e09c263592399fdb`
- deployment: `dpl_v4W4CAABooUMYYjnTgKpHhFCXr55`
- state: `READY`
- merged-main required `build`: success
- reviewed post-deploy Vercel `error`/`fatal` log window: no matching events

The stable alias remains `https://growthops-crm.vercel.app`. The much older `dpl_JWXVvjCdjRF59gMrZycDUJEXYP7G` remains historical POST-200/server-secret-repair evidence, not the current frontend/runtime artifact authority.

### Cloudflare Pages

Cloudflare Pages uses `main` as Production and the same canonical build/output contract. For `main@23f3bbd7e491357d2533a2c5e09c263592399fdb`, both merged-main required `build` and Cloudflare Pages main deployment completed successfully. The Cloudflare deployment/check identifier for this accepted main is `75b2bfbb-0cf6-467a-bd6b-e701e0bdb542`.

Cloudflare Preview must not silently use Production Supabase. Standard Preview hosts require an explicit isolated staging Supabase URL when a server secret is active; otherwise runtime/build is expected to fail closed. Do not weaken this guard just to make Preview deploy.

Historical fail-closed evidence is retained: on 2026-08-25 Vercel Preview deployment `dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY` failed with `PREVIEW_SECRET_BOUNDARY_FAILED` while a Production server secret was still present in Preview. The guard did not print the secret. This is historical evidence that the boundary worked, not evidence that cleanup remains open.

**Preview Production-secret cleanup accepted on 2026-08-27.** Cloudflare Preview no longer carries `GROWTHOPS_SUPABASE_SECRET_KEY`; Cloudflare Production retains its encrypted Production binding. `Vercel Preview: no project environment variables`; Production retained its hidden Production-only server identity. Issue #92 remains closed / completed.

## Historical / maintenance rules

Historical P0/P1/P2/P3/P4/P5/Post-P5 files intentionally retain what was true at their checkpoints. Do not reinterpret old hashes, grant counts, deployment IDs, or “next phase” text as the current Production contract when they conflict with this file or the database authority.

Maintenance rules:

1. Prefer small single-purpose PRs with narrow diffs and explicit rollback where relevant.
2. Do not delete files merely because names appear historical; prove they are outside build, CI, runtime and documentation dependencies first. The rejected #179 cleanup remains evidence that apparently obsolete Vue probe material can still be imported by active tests.
3. Do not weaken Preview/Production origin isolation, same-origin BFF/session rules, credential reveal boundaries, CRM/default ACL guards, browser-CDN removal, eval-free CSP, or compiler-free Vue just to simplify another change.
4. Keep `ROLLBACK.md`, `CURRENT_DATABASE_AUTHORITY_20260830.md`, `P0_MIGRATION_LEDGER.md`, and this file aligned when architecture, privilege boundaries, recovery strategy, or accepted hosting/runtime checkpoints materially change.
5. Issues #91, #92, #93 and #95 remain closed / completed. Recovery-target keep/pause/delete remains a separate lifecycle choice and is not implied by technical acceptance closure.
