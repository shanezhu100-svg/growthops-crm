from pathlib import Path
import re

root = Path(__file__).resolve().parent
ledger = (root / 'docs/cloudflare-migration/P0_MIGRATION_LEDGER.md').read_text(encoding='utf-8')
appendix = (root / 'docs/cloudflare-migration/P0_MIGRATION_LEDGER_20260825_APPENDIX.md').read_text(encoding='utf-8')
current_state = (root / 'docs/cloudflare-migration/CURRENT_STATE.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')
current_db = (root / 'docs/cloudflare-migration/CURRENT_DATABASE_AUTHORITY_20260830.md').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

latest_version = '20260830071649'
latest_name = 'client_account_safe_summary_correspondence'
latest_file = 'supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql'
latest_rollback = 'supabase/rollback/20260830071649_client_account_safe_summary_correspondence.sql'
primary_hash = '8ff7dd1447bf2cea9802438f91e8e1d3bf34bc7f7b4878592dd2eca8b06da7f9'
guard_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'
public_recovery_hash = 'b89328f5548d4787a650b7f079bc1843125cc7c1b550d959a8cb4df2b2df04f2'
predecessor_version = '20260825075808'
predecessor_name = 'post_p5_rate_limit_concurrency'
predecessor_primary = '77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65'
predecessor_wider = 'a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab'

# Production was re-read on 2026-08-30: 52 migration rows, while the known
# 2026-08-13/14 remote-history-only gap remains exactly eleven entries.
remote_versions = re.findall(r'^\| `([0-9]{14})` \|', ledger, flags=re.MULTILINE)
require(len(remote_versions) == 52,
        f'consolidated ledger must contain exactly 52 remote migration table rows, found {len(remote_versions)}')
require(len(set(remote_versions)) == 52,
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

latest_row = f'| `{latest_version}` | `{latest_name}` | `{latest_file}` |'
require(latest_row in ledger,
        'latest Production migration must map to genuine repository SQL')
require((root / latest_file).is_file(),
        'latest Production migration repository SQL is missing')
require((root / latest_rollback).is_file(),
        'latest Production migration rollback SQL is missing')

# Every migration SQL path cited by the current consolidated ledger must resolve.
listed_migration_files = sorted(set(re.findall(r'`(supabase/migrations/[^`]+\.sql)`', ledger)))
require(listed_migration_files, 'consolidated ledger contains no repository migration file mappings')
for relpath in listed_migration_files:
    require((root / relpath).is_file(), f'ledger references missing migration SQL: {relpath}')

require('Last consolidated from Production: 2026-08-30' in ledger,
        'main migration ledger must record current Production consolidation date')
require('consolidated current remote migration-history authority' in ledger,
        'main migration ledger must remain the current remote-history authority')
require('Consolidated into `P0_MIGRATION_LEDGER.md`: 2026-08-25' in appendix,
        '8/25 appendix must remain marked as consolidated historical evidence')
require('use the main ledger as the current migration-history authority' in appendix,
        'appendix must continue to defer current authority to the main ledger')

for source, label in ((ledger, 'P0_MIGRATION_LEDGER'), (current_db, 'CURRENT_DATABASE_AUTHORITY_20260830')):
    require(latest_version in source and latest_name in source,
            f'{label} missing current Production migration head')
    require(primary_hash in source, f'{label} missing current primary fingerprint')
    require(guard_hash in source, f'{label} missing current guard fingerprint')
    require(public_recovery_hash in source, f'{label} missing current wider-public fingerprint')

# Historical current-state/recovery documents retain prior checkpoint details;
# the 2026-08-30 DB-specific override must explicitly supersede those fields while
# preserving the accepted v3 artifact as a 51-migration base plus one forward migration.
require('database-specific override' in current_db,
        'current DB authority must explicitly override older database checkpoint text')
for fragment in (
    predecessor_version, predecessor_name, predecessor_primary, predecessor_wider,
    'Recovery Bundle v3', '51-migration recovery base', latest_file,
    'future-object default-privilege hardening',
):
    require(fragment in current_db, f'current DB authority missing continuity marker: {fragment}')

# Existing historical phase gates intentionally continue to find their accepted
# predecessor in CURRENT_STATE/CURRENT_RECOVERY; do not erase old accepted evidence.
for source, label in ((current_state, 'CURRENT_STATE'), (current_recovery, 'CURRENT_RECOVERY_VERIFICATION')):
    require(predecessor_version in source and predecessor_name in source,
            f'{label} lost predecessor migration evidence')
    require(predecessor_primary in source,
            f'{label} lost predecessor primary fingerprint evidence')
    require(guard_hash in source,
            f'{label} lost guard fingerprint continuity')

require('pending the next consolidated historical-ledger refresh' not in current_state,
        'CURRENT_STATE still claims migration-ledger consolidation is pending')
require('P0_MIGRATION_LEDGER.md` is now the consolidated current remote migration-history' in current_state,
        'CURRENT_STATE must name the consolidated main ledger as current authority')
require('point-in-time acceptance evidence' in current_state,
        'CURRENT_STATE must preserve the appendix as historical evidence')

require(build.count('python3 test_migration_ledger_recovery.py') == 1,
        'canonical build must run migration-ledger recovery gate exactly once')

print(
    'MIGRATION_LEDGER_RECOVERY_OK: remote=52; historical-gap=11; '
    'latest=20260830071649; latest-repo-backed=true; v3-base=51+forward=1; '
    'recovery-hashes=primary+guard+wider-public'
)
