# P1 Cloudflare Pages Preview Status (Historical)

Last reviewed: 2026-08-24

> Status: completed historical phase. This file preserves the P1 migration evidence and checklist; it is no longer the current project checklist. The repository has since advanced through P2-A, P2-B, P5, and Post-P5 hardening. Current merge validation is defined by the canonical `sh build.sh && python3 cloudflare_p1_verify.py` GitHub Actions gate.

## P0 gate status

P0 is **closed for the migration gate**.

- [x] Recovery baseline and rollback inventory merged (PR #14).
- [x] Live schema/security manifest and deterministic fingerprint merged (PR #15).
- [x] Zero-cost isolated Supabase recovery rehearsal completed and merged (PR #17).
- [x] Isolated recovery target matched Production exactly: `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`.
- [x] Synthetic ADMIN/OPS login, state save/load, Vault write, unlock, scalar password/2FA reveal, OPS denial and audit non-leakage acceptance passed.
- [x] Synthetic test data and test Vault secret were removed; post-cleanup CRM/Vault test counts returned to zero.
- [x] Production was re-fingerprinted after the rehearsal and remained unchanged.

A raw offline `pg_dump` artifact was not produced and is not claimed. It may be added later as portability hardening; the adopted P0 migration gate is the verified zero-download isolated Supabase recovery proof.

## Completed P1 preflight

- [x] P1 repository preparation branch: `cloudflare-p1-pages-preview-20260821`.
- [x] P1 branch refreshed onto current `main` after P0 closure.
- [x] Cloudflare Pages setup runbook added: `P1_PAGES_PREVIEW.md`.
- [x] `cloudflare_p1_verify.py` limited to Cloudflare output parity only: `dist/` presence plus five frozen production artifact SHA-256 values.
- [x] Credential / HttpOnly / RPC security remains owned by `sh build.sh` and its existing authoritative tests.
- [x] Obsolete GitHub Pages deployment workflow `.github/workflows/static.yml` removed from the P1 branch.
- [x] Suspected unused finalizers/tests recorded as post-migration dead-code candidates; nothing in that group was deleted during P1/P2. Those candidates were later re-audited after the freeze ended, and the proven-unused files were removed in PR #61 and PR #62 under the complete canonical build gate.
- [x] P1 introduces no database migration, RPC grant change, authentication change, credential movement, API split, CSP tightening or production DNS change.
- [x] GitHub App `Cloudflare Workers and Pages` is installed and limited to `Only select repositories`, with only `growthops-crm` selected.
- [x] Cloudflare Pages Git integration recognizes `shanezhu100-svg/growthops-crm`.
- [x] Cloudflare Pages project created with production branch `main`, framework preset `None`, build command `sh build.sh && python3 cloudflare_p1_verify.py`, output directory `dist`, and no real CRM custom domain attached.

## Initial production-branch build

The first Pages build used `main` and failed only after `sh build.sh` completed because `main` did not yet contain `cloudflare_p1_verify.py`; that verifier intentionally existed only in PR #16 until P1 acceptance.

This was not a CRM/runtime failure. PR #16 was not merged early, the verifier was not weakened, and `main` remained the Pages production branch. The P1 branch was then updated to trigger the correct Cloudflare Preview deployment.

## Cloudflare Preview acceptance

- [x] Preview branch: `cloudflare-p1-pages-preview-20260821`.
- [x] First fully inspected Preview source commit: `41bf7a8504b5f284117343781c1e0f4d77f2ae60`.
- [x] First fully inspected Cloudflare deployment ID: `8f81eec8-2957-4d82-a77a-1fc403be86a6`.
- [x] First fully inspected Preview URL: `https://8f81eec8.growthops-crm.pages.dev/`.
- [x] Build command executed exactly: `sh build.sh && python3 cloudflare_p1_verify.py`.
- [x] Existing `build.sh` runtime/security gates passed on Cloudflare, including HttpOnly session and v5-only reveal checks.
- [x] Build log printed `CLOUDFLARE_P1_OUTPUT_PARITY_OK: dist=present; key_artifacts=5; production_hashes=match`.
- [x] Cloudflare published all static assets successfully and reported `Success: Your site was deployed!`.
- [x] Cloudflare reported no `/functions` directory, confirming P1 remained static-only and did not accidentally move `/api/crm`.
- [x] Desktop `.pages.dev` page loaded and visually matched the current Vercel baseline for the tested shell/dashboard layout.
- [x] Mobile visual acceptance passed using the user-provided DevTools responsive screenshot at `400 × 654`: mobile header, hero/dashboard card, two-column KPI cards, margins, scrolling and content containment rendered correctly with no visible horizontal overflow, clipping or overlap.
- [x] Final single-commit merge candidate `81503135d7a1f162f959850b6816de30028794dd` received a successful Cloudflare Preview before this status-only update; Cloudflare bot reported `Deploy successful`, with deployment URL `https://7cfc7e07.growthops-crm.pages.dev` and branch Preview URL `https://cloudflare-p1-pages-preview.growthops-crm.pages.dev`.
- [x] Post-Preview Supabase structural/security cross-check remained on the frozen baseline shape: 9 CRM tables, 40 CRM functions, 26 CRM indexes, 5 business triggers, 12 anon-executable CRM RPCs, 0 authenticated-executable CRM RPCs, 40 service-role-executable CRM RPCs, 9 RLS-enabled CRM tables, 0 CRM policies, and 1 Vault row.
- [x] The full deterministic Production fingerprint immediately before Preview remained `258 / d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`; P1 performed no database writes.
- [x] Vercel Production rollback target remained `READY`, and no Production runtime error cluster was found in the checked one-hour window.

## Historical P1 merge gate

At the time of P1, all functional acceptance items were complete and the status-only commit itself was required to receive green Cloudflare and Vercel Preview checks before PR #16 was marked Ready and merged.

The historical rule was: do not merge if the PR head moves after those checks; merge only with the expected head SHA. The repository continues to use expected-head merges for current small PRs, while current PR execution is validated by the secret-free GitHub canonical gate and main-only Vercel Git deployment policy.

## Historical next transition

P1's next planned transition was P2-A:

**move the existing same-origin `/api/crm` behavior 1:1 to Cloudflare Worker/Pages Functions before any API split or Supabase privilege tightening.**

That transition is complete. P2-A was followed by P2-B server identity, P5 RPC revocation, and Post-P5 hardening; their dedicated documents and the current canonical build gates are authoritative for those later controls.
