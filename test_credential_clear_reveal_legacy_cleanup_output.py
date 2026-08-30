from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECURITY = (ROOT / 'dist' / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
FINALIZER = (ROOT / 'credential_clear_reveal_legacy_cleanup_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit('CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_TEST_FAILED: ' + message)


require('applyCredentialStatusToCards' not in SECURITY,
        'retired credential-status renderer reference remains in final runtime')
require('applyAccountSafeSummaryToCards();' in SECURITY,
        'current account-safe-summary renderer call missing')
require("expected exactly one retired call" in FINALIZER,
        'finalizer no longer fails closed on legacy call count drift')
require("retired renderer definition unexpectedly survived v6 cleanup" in FINALIZER,
        'finalizer no longer checks v6 ownership boundary')

finalizer_call = 'python3 credential_clear_reveal_legacy_cleanup_finalize.py'
test_call = 'python3 test_credential_clear_reveal_legacy_cleanup_output.py'
correspondence_call = 'python3 client_account_correspondence_finalize.py'
if BUILD.count(finalizer_call) != 1 or BUILD.count(test_call) != 1:
    raise SystemExit('CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_TEST_FAILED: build wiring count drift')
require(BUILD.index(finalizer_call) > BUILD.index(correspondence_call),
        'cleanup must run after client-account correspondence finalization')
require(BUILD.index(test_call) > BUILD.index(finalizer_call),
        'cleanup output test must run after cleanup finalizer')

print(
    'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_TEST_OK: '
    'retired-reference=absent; current-safe-summary=present; build-order=guarded'
)
