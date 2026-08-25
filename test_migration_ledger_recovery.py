from pathlib import Path
import re

root = Path(__file__).resolve().parent
ledger = (root / 'docs/cloudflare-migration/P0_MIGRATION_LEDGER.md').read_text(encoding='utf-8')
appendix = (root / 'docs/cloudflare-migration/P0_MIGRATION_LEDGER_20260825_APPENDIX.md').read_text(encoding='utf-8')
current_state = (root / 'docs/cloudflare-migration/CURRENT_STATE.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

latest_version = '20260825075808'
latest_name = 'post_p5_rate_limit_concurrency'
latest_file = 'supabase/migrations/20260825_post_p5_rate_limit_concurrency.sql'
primary_hash = '77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65'
guard_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'
public_recovery_hash = 'a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab'

# Production was re-read on 2026-08-25: 51 migration rows, with the known
# 2026-08-13/14 gap still exactly eleven remote-history-only entries.
remote_versions = re.findall(r'^\| `([0-9]{14})` \|', ledger, flags=re.MULTILINE)
require(len(remote_versions) == 51,
        f'consolidated ledger must contain exactly 51 remote migration table rows, found {len(remote_versions)}')
require(len(set(remote_versions)) == 51,
        'consolidated ledger must not duplicate remote migration versions across its tables')
require(remote_versions[0] == '20260813095251',
        'consolidated ledger first remote migration changed unexpectedly')
require(remote_versions[-1] == latest_version,
        'consolidated ledger latest remote migration must match Production re-read')
require(remote_versions == sorted(remote_versions),
        'consolidated ledger remote migration rows must remain chronologically ordered')

require(ledger.count('remote-history-only; original SQL absent from current repo') == 11,
        'historical remote-history-only gap must remain exactly eleven entries')
require('The unresolved historical gap remains exactly the eleven 2026-08-13/14 entries' in ledger,
        'consolidated ledger must preserve the exact historical-gap statement')
require('do not blur that known gap with later forward migrations' in ledger,
        'consolidated ledger must distinguish known historical gaps from repository-backed forward migrations')

latest_row = (
    f'| `{latest_version}` | `{latest_name}` | '
    f'`{latest_file}` |'
)
require(latest_row in ledger,
        'latest Production migration must map to its genuine repository SQL in the consolidated ledger')
require((root / latest_file).is_file(),
        'latest Production migration repository SQL is missing')

# Every migration SQL path cited by the current consolidated ledger must resolve
# to a real repository file; this catches silent documentation/file drift.
listed_migration_files = sorted(set(re.findall(r'`(supabase/migrations/[^`]+\.sql)`', ledger)))
require(listed_migration_files,
        'consolidated ledger contains no repository migration file mappings')
for relpath in listed_migration_files:
    require((root / relpath).is_file(), f'ledger references missing migration SQL: {relpath}')

require('Last consolidated from Production: 2026-08-25' in ledger,
        'main migration ledger must record its Production consolidation date')
require('the appendix is no longer required to determine the current migration head' in ledger,
        'main migration ledger must be self-sufficient for the current migration head')
require('Consolidated into `P0_MIGRATION_LEDGER.md`: 2026-08-25' in appendix,
        '8/25 appendix must be marked as consolidated historical evidence')
require('use the main ledger as the current migration-history authority' in appendix,
        'appendix must defer current authority to the consolidated main ledger')

for source, label in (
    (ledger, 'P0_MIGRATION_LEDGER'),
    (current_state, 'CURRENT_STATE'),
    (current_recovery, 'CURRENT_RECOVERY_VERIFICATION'),
):
    require(latest_version in source and latest_name in source,
            f'{label} missing current Production migration head')

for recovery_hash, label in (
    (primary_hash, 'primary'),
    (guard_hash, 'three-guard'),
    (public_recovery_hash, 'wider-public'),
):
    require(recovery_hash in ledger,
            f'consolidated ledger missing current {label} recovery fingerprint')

require('pending the next consolidated historical-ledger refresh' not in current_state,
        'CURRENT_STATE still claims migration-ledger consolidation is pending')
require('P0_MIGRATION_LEDGER.md` is now the consolidated current remote migration-history' in current_state,
        'CURRENT_STATE must name the consolidated main ledger as current authority')
require('point-in-time acceptance evidence' in current_state,
        'CURRENT_STATE must preserve the appendix as historical evidence rather than delete it')

require(build.count('python3 test_migration_ledger_recovery.py') == 1,
        'canonical build must run migration-ledger recovery gate exactly once')

print(
    'MIGRATION_LEDGER_RECOVERY_OK: remote=51; historical-gap=11; '
    'latest=20260825075808; latest-repo-backed=true; appendix=historical; '
    'recovery-hashes=primary+guard+wider-public'
)
