# P1 Cloudflare Pages Preview

Checkpoint date: 2026-08-22

P1 moves only the static build/hosting surface to Cloudflare Pages Preview. It must not change Supabase, CRM authentication, credential reveal, RPC grants, production DNS, or the current Vercel rollback target.

## P0 prerequisite

The P0 isolated cloud recovery gate is complete and merged to `main` via PR #17.

- Production/test CRM schema-security fingerprint parity: `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`
- Synthetic ADMIN/OPS, state save/load, Vault, unlock, scalar password/2FA reveal and audit non-leakage acceptance: PASS
- Production Vault plaintext copied/decrypted for the rehearsal: none
- Isolated recovery test data after cleanup: zero

See `P0_CLOUD_RECOVERY_REHEARSAL.md` for the accepted recovery evidence. P1 therefore proceeds from a verified recoverable baseline.

## Cloudflare project settings

Use Cloudflare Pages with Git integration.

- Git provider: GitHub
- Repository: `shanezhu100-svg/growthops-crm`
- Root directory: repository root
- Framework preset: none / no framework
- Build command: `sh build.sh && python3 cloudflare_p1_verify.py`
- Build output directory: `dist`
- Production custom domain: **do not attach yet**
- Existing Vercel production: **do not remove or modify**

Cloudflare Pages determines build success from the build command exit code. The existing `build.sh` remains the authoritative application build/security gate. It already owns Credential, HttpOnly session, RPC surface, and runtime security tests. `cloudflare_p1_verify.py` does not reimplement those tests; it is a read-only Cloudflare P1 parity check limited to `dist/` existence and the five frozen production artifact hashes. It does not modify `dist`.

## Branch control

Recommended safe setup:

1. Connect the repository to Pages.
2. Keep `main` as the Pages project production branch only for the project-level `.pages.dev` origin; do not attach the real CRM production domain.
3. Under branch controls, enable Preview builds only for the migration branches that need validation, starting with:
   - `cloudflare-p1-pages-preview-20260821`
   - later `cloudflare-p2-*` branches as required
4. If desired after initial setup, disable automatic production-branch deployments while the migration is in Preview-only mode.

A GitHub PR from a branch in the same repository should receive a Cloudflare Pages preview URL when Git integration and preview branch controls allow it.

## Do not add a hand-written Wrangler config yet

P1 intentionally does not add `wrangler.jsonc` / `wrangler.toml`.

For an existing dashboard-configured Pages project, download the project configuration before making Wrangler the configuration source of truth. A hand-written Wrangler file could silently diverge from the dashboard project.

When/if the project later adopts Wrangler-managed Pages configuration, the output directory must correspond to `./dist`, but that transition is a separately reviewed change.

## P1 build parity acceptance

A Cloudflare Pages Preview build must show all existing `build.sh` gates passing. Those existing gates remain the source of truth for application/security behavior.

After `build.sh`, the Cloudflare P1 verifier checks only these final frozen artifacts:

- `dist/index.html`: `941be51fcaf60acd0bb350c1822260f24555340fb2d719effe0f339c3b69a1e5`
- `dist/cloud-adapter.js`: `2a5b5da0f94ba66a2b58ed64b923e0167e7723eb7ccccd3c6384dfbeb471a2a6`
- `dist/cloud-security-hotfix.js`: `ebe0cc3fe1ff4d40481973b188a799700b786a958ef492a36b5b6ed541617a25`
- `dist/cloud-p1-overrides.js`: `e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab`
- `dist/cloud-ui-action-bridge.js`: `b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7`

The Cloudflare build command must report:

`CLOUDFLARE_P1_OUTPUT_PARITY_OK`

## Supabase no-drift acceptance

P1 must not modify Supabase.

Run the read-only fingerprint query before/after P1:

`supabase/baseline/p0_schema_security_fingerprint.sql`

Expected P0/P1 result:

- inventory lines: `258`
- schema/security SHA-256: `d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`

Also re-check:

- Vault row count remains `1` unless an intentional CRM credential change occurred independently of the migration.
- workspace sensitive-key matches remain `0`.
- audit sensitive payload-value matches remain `0`.

## What P1 can validate

P1 validates that Cloudflare can build and serve the exact static CRM output without layout/resource drift:

- HTML loads
- JS/CSS/font/static assets load
- login shell renders
- desktop layout matches the Vercel baseline
- mobile layout matches the Vercel baseline
- all existing `build.sh` application/security gates pass unchanged in Cloudflare's build environment

## Deliberate P1 limitation

The current CRM API is a Vercel Function at same-origin `/api/crm`. A pure Pages static Preview does not provide that Vercel Function at the new `.pages.dev` origin.

Therefore **do not claim authenticated login/state/Vault flows are accepted in P1 static Preview**. Those become testable in P2-A, when the existing `/api/crm` contract is moved 1:1 to Cloudflare Worker/Pages Functions without changing its security behavior.

This separation is intentional: P1 tests hosting/build parity; P2 tests API/session parity.

## P1 hard prohibitions

Do not in P1:

- change `build.sh` behavior;
- change `api/crm.js` behavior;
- add a new authentication design;
- move CRM Token back to browser-readable storage;
- add Cloudflare KV/D1/R2 for customer credentials;
- change Supabase schema or data;
- revoke existing transitional anon RPC grants;
- split `/api/crm` into multiple APIs;
- tighten CSP beyond the current production policy;
- attach/cut the real production CRM domain;
- remove the frozen Vercel production rollback target.

## Exit criteria

P1 is complete only when:

1. Cloudflare Pages project is connected to the GitHub repository.
2. A migration-branch Preview deployment is successful.
3. `sh build.sh` passes unchanged on Cloudflare.
4. `cloudflare_p1_verify.py` passes in the Cloudflare build.
5. Static layout/assets are verified on desktop and mobile.
6. Supabase fingerprint remains unchanged.
7. Vercel production remains healthy and available for rollback.

Then proceed to P2-A: migrate the existing same-origin `/api/crm` behavior 1:1 to Cloudflare before any API redesign.
