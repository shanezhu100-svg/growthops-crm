from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'

security = SECURITY.read_text(encoding='utf-8')
legacy_call = "    applyCredentialStatusToCards();\n"
current_call = "    applyAccountSafeSummaryToCards();\n"
legacy_definition = "const applyCredentialStatusToCards"

# credential_ui_v5 temporarily retains the old boolean-status renderer as a no-op
# compatibility marker. credential_ui_v6 intentionally removes that definition,
# but the historical clearReveal() call survived. That leaves a latent ReferenceError
# on visibility/page lifecycle paths. Final output must contain only the current
# account-safe-summary renderer.
if security.count(legacy_call) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'expected exactly one retired call, found {security.count(legacy_call)}'
    )
if legacy_definition in security:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'retired renderer definition unexpectedly survived v6 cleanup'
    )
if security.count(current_call) < 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'current account-safe-summary renderer call missing'
    )

security = security.replace(legacy_call, '', 1)
if 'applyCredentialStatusToCards' in security:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'retired renderer reference remains after cleanup'
    )

SECURITY.write_text(security, encoding='utf-8')
print(
    'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_OK: '
    'retired-status-call=removed; current-safe-summary=preserved; security=' +
    hashlib.sha256(SECURITY.read_bytes()).hexdigest()
)
