# Dead-code candidates — defer until Cloudflare is stable

Last reviewed: 2026-08-21

This is a holding list only. **Do not delete these files during Cloudflare P1/P2.** The current migration baseline must remain stable.

## Current candidates

- `credential_refresh_eye_finalize.py`
- `test_credential_refresh_eye_output.py`
- `ui_runtime_diagnostic_finalize.py`
- `test_ui_runtime_diagnostic_output.py`

Why they are candidates:

- Current `build.sh` does not invoke either finalizer or either paired test.
- Their responsibilities overlap with later credential v5/v6 runtime handling or optional diagnostics.
- They are not required to simplify P1/P2 and deleting them now would create unnecessary baseline churn.

## Required deletion gate

After Cloudflare P1/P2 is stable, perform one repository-wide reference scan before deleting anything. Confirm all of the following for each candidate:

1. `build.sh` and CI/workflows do not execute it.
2. No Python file imports/executes it.
3. No generated/runtime JS or HTML depends on its output.
4. No deployment/debug runbook still requires it.
5. Removing it leaves the full authoritative build/test suite green.

Delete confirmed dead files together in one dedicated technical-debt PR; do not mix that cleanup with Cloudflare migration/security changes.
