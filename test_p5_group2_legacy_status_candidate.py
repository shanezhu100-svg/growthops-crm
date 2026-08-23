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

# Group 1 predecessor and frozen baseline must remain recorded.
require('Group 1 predecessor gate is complete' in doc, 'candidate doc does not record completed Group1 predecessor gate')
require('e5314a3c4cdf33c5bc2a42bb380fe029321d153e' in doc, 'candidate doc missing accepted Group1 main SHA')
require('258 / beb4efcaa8d85d13fc826cf98a66ea8981c3d4f3f4ff2c930acca3df196ef07e' in doc, 'candidate doc missing accepted Group1 fingerprint')

# Final Group 2 evidence must record the exact Production migration and post-change baseline.
require('20260823062545 / p5_group2_revoke_legacy_credential_status_anon_exec' in doc, 'candidate doc missing applied Group2 migration record')
require('target `anon=false`' in doc, 'candidate doc missing post-change anon=false evidence')
require('anon EXECUTE: `9` (`10 -> 9`)' in doc, 'candidate doc missing post-change anon total')
require('258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224' in doc, 'candidate doc missing post-Group2 fingerprint')
require('77d5cfdd-ec0b-4305-b555-2ee275e98318' in doc, 'candidate doc missing Cloudflare exact-head evidence')
require('dpl_A2pkY3p3HksUa4G3W974kMQ54TGy' in doc, 'candidate doc missing Vercel exact-head evidence')

print(
    'P5_GROUP2_LEGACY_STATUS_CANDIDATE_OK: '
    'legacy-status=absent-from-bffs+forbidden-in-final-runtime; '
    'safe-summary=preserved; group1=accepted; production-change=applied+verified'
)
