from pathlib import Path

root = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise SystemExit(message)


vercel_bff = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare_bff = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
v6_finalizer = (root / 'credential_ui_v6_finalize.py').read_text(encoding='utf-8')
v6_test = (root / 'test_credential_ui_v6_output.py').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'P5_GROUP2_LEGACY_STATUS_CANDIDATE.md').read_text(encoding='utf-8')

legacy_rpc = 'crm_client_credential_status'
safe_summary = 'crm_client_account_safe_summary'

# The legacy status RPC must not be browser-reachable through either BFF.
require(legacy_rpc not in vercel_bff, 'legacy credential status RPC is still present in Vercel BFF')
require(legacy_rpc not in cloudflare_bff, 'legacy credential status RPC is still present in Cloudflare BFF')

# The replacement safe-summary path must remain browser-reachable.
require(safe_summary in vercel_bff, 'safe-summary RPC missing from Vercel BFF')
require(safe_summary in cloudflare_bff, 'safe-summary RPC missing from Cloudflare BFF')

# Final runtime generation and output tests must explicitly reject the legacy path.
require(f'"{legacy_rpc}"' in v6_finalizer, 'v6 finalizer does not explicitly forbid legacy credential status RPC')
require(f'"{legacy_rpc}"' in v6_test, 'v6 output test does not explicitly forbid legacy credential status RPC')
require(safe_summary in v6_finalizer, 'v6 finalizer no longer requires safe-summary RPC')
require(safe_summary in v6_test, 'v6 output test no longer requires safe-summary RPC')

# This preparation stage is deliberately non-mutating: no forward revoke is shipped here.
require('No forward `REVOKE` migration is included yet.' in doc, 'candidate doc lost no-migration guard')
require('must not be merged ahead of P5 Group 1 acceptance' in doc, 'candidate doc lost predecessor gate')

print(
    'P5_GROUP2_LEGACY_STATUS_CANDIDATE_OK: '
    'legacy-status=absent-from-bffs+forbidden-in-final-runtime; '
    'safe-summary=preserved; production-change=none'
)
