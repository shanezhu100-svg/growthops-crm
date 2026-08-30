# Dead-code cleanup record

Last reviewed: 2026-08-30

The Cloudflare P1/P2 baseline freeze has ended. P2-B completed real Cloudflare and Vercel Preview acceptance, and the repository has since advanced through P5/Post-P5 hardening and the accepted Vue 3.5.41 runtime-only/eval-free cutover. Historical candidates are removed only after a fresh reference audit and a complete authoritative CRM Build Gate.

## Removed candidates

- `credential_refresh_eye_finalize.py`
- `test_credential_refresh_eye_output.py`
- `ui_runtime_diagnostic_finalize.py`
- `test_ui_runtime_diagnostic_output.py`
- `ui-runtime-diagnostic.js`
- `test_vue_runtime_final_stage_probe.py`

## Deletion-gate evidence

For the original four build-time candidates:

1. `build.sh` did not execute either finalizer or either paired test.
2. The sole GitHub Actions workflow (`.github/workflows/crm-build.yml`) executed only the canonical `sh build.sh && python3 cloudflare_p1_verify.py` gate and did not name these files.
3. The credential refresh/eye responsibilities had been superseded by the canonical v5/v6 credential UI pipeline plus the later eye self-heal output gate.
4. The runtime diagnostic finalizer was never part of the canonical production build; production uses the normal UI action/runtime path without injecting `ui-runtime-diagnostic.js`.

For `ui-runtime-diagnostic.js`:

1. Its only historical injector, `ui_runtime_diagnostic_finalize.py`, was removed after the full canonical gate proved it was outside the production build.
2. Narrow repository searches for `ui-runtime-diagnostic.js`, `growthops-ui-runtime-diag`, `client-nav-diag-v2`, and `UI DIAG v2` found no build, workflow, documentation, or runtime references.
3. The script was a standalone diagnostic overlay that monkey-patched client navigation functions and was not part of the canonical production artifact path.
4. This follow-up cleanup must merge only after the complete authoritative CRM Build Gate passes unchanged.

For `test_vue_runtime_final_stage_probe.py`:

1. PR #178 replaced its GitHub-only template probe with the accepted portable `vue_runtime_only_finalize.py` + `vue_runtime_compiled_marker_finalize.py` + `test_vue_runtime_only_output.py` cutover.
2. `.github/workflows/crm-build.yml` now repeats `test_vue_runtime_only_output.py` after the canonical build and then runs the real Chromium mount and client-form credential DOM regressions; it no longer calls the final-stage probe.
3. `test_ci_quota_guard.py` explicitly treats `test_vue_runtime_final_stage_probe.py` as `legacy_final_probe` and requires its call count to remain zero in both `build.sh` and the GitHub workflow.
4. Narrow repository reference search found no remaining build, workflow, runtime, or current-document consumer of the retired probe.
5. The accepted runtime-only production path is independently guarded by the 28-artifact Cloudflare verifier, compiler-asset absence check, eval-free CSP gate, VM smoke, real Chromium mount smoke, and credential DOM regression.

## Remaining candidates

None recorded here. Any future cleanup candidate must be re-audited against the then-current build, CI, generated runtime, deployment runbooks, and full regression gate before deletion.
