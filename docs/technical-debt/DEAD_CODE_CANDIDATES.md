# Dead-code cleanup record

Last reviewed: 2026-08-24

The Cloudflare P1/P2 baseline freeze has ended. P2-B completed real Cloudflare and Vercel Preview acceptance, and the repository has since advanced through P5/Post-P5 hardening. The four historical candidates below were therefore re-audited for removal in a dedicated technical-debt change.

## Removed candidates

- `credential_refresh_eye_finalize.py`
- `test_credential_refresh_eye_output.py`
- `ui_runtime_diagnostic_finalize.py`
- `test_ui_runtime_diagnostic_output.py`

## Deletion-gate evidence

Before removal:

1. `build.sh` did not execute either finalizer or either paired test.
2. The sole GitHub Actions workflow (`.github/workflows/crm-build.yml`) executed only the canonical `sh build.sh && python3 cloudflare_p1_verify.py` gate and did not name these files.
3. The credential refresh/eye responsibilities had been superseded by the canonical v5/v6 credential UI pipeline plus the later eye self-heal output gate.
4. The runtime diagnostic finalizer was never part of the canonical production build; production uses the normal UI action/runtime path without injecting `ui-runtime-diagnostic.js`.
5. This cleanup must merge only after the complete authoritative CRM Build Gate passes unchanged, proving no generated/runtime artifact or test dependency remains.

## Remaining candidates

None recorded here. Any future cleanup candidate must be re-audited against the then-current build, CI, generated runtime, deployment runbooks, and full regression gate before deletion.
