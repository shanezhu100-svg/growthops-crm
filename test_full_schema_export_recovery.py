from pathlib import Path

root = Path(__file__).resolve().parent
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
current_state = (root / 'docs/cloudflare-migration/CURRENT_STATE.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

current_migration = '20260825075808 / post_p5_rate_limit_concurrency'
primary_hash = '77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65'
guard_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'

for source, label in (
    (full_export, 'FULL_SCHEMA_EXPORT'),
    (current_state, 'CURRENT_STATE'),
    (current_recovery, 'CURRENT_RECOVERY_VERIFICATION'),
):
    require(current_migration in source, f'{label} missing current Production migration anchor')
    require(primary_hash in source, f'{label} missing current primary CRM fingerprint')
    require(guard_hash in source, f'{label} missing current supplemental guard fingerprint')

require('The full schema-only export is **not yet complete**.' in full_export,
        'FULL_SCHEMA_EXPORT must remain explicitly open until a real portable dump exists')
require('supabase db dump --db-url "$SUPABASE_DB_URL" -f schema.sql' in full_export,
        'FULL_SCHEMA_EXPORT missing the authorized Supabase CLI schema-only path')
require('A service-role/API secret is **not** a PostgreSQL database password' in full_export,
        'FULL_SCHEMA_EXPORT must forbid substituting the service-role secret for a DB password')
require('a generated catalog/DDL manifest or manually reconstructed SQL' in full_export,
        'FULL_SCHEMA_EXPORT must reject catalog reconstruction as dump completion')
require('Do not mark this deliverable complete until a real export artifact has been produced' in full_export,
        'FULL_SCHEMA_EXPORT must require an actual export artifact')
require('known 2026-08-13/14 migration-history gap remains' in full_export,
        'FULL_SCHEMA_EXPORT must preserve the unresolved historical migration-gap warning')
require('no database password/credential-bearing connection string is available' in full_export,
        'FULL_SCHEMA_EXPORT must record the current credential blocker')
require('no Supabase CLI / Docker / Podman / `pg_dump` / `psql` toolchain' in full_export,
        'FULL_SCHEMA_EXPORT must record the current toolchain blocker')

# Historical pre-concurrency values may be retained only when explicitly described
# as historical, never as the current verification checkpoint.
old_hash = 'bffaf123425bc7bddf02ecf00132848a5bfc4248e44395a5283c8ca9706b97f1'
old_migration = '20260825040850 / post_p5_public_default_privilege_guard'
require(old_hash in full_export and 'historical pre-concurrency checkpoints' in full_export,
        'FULL_SCHEMA_EXPORT must label the preceding primary hash as historical')
require(old_migration in full_export and 'historical pre-concurrency checkpoints' in full_export,
        'FULL_SCHEMA_EXPORT must label the preceding migration head as historical')

require(build.count('python3 test_full_schema_export_recovery.py') == 1,
        'canonical build must execute full-schema recovery truth gate exactly once')

print(
    'FULL_SCHEMA_EXPORT_RECOVERY_OK: status=open; '
    'portable-dump=required; catalog-substitute=forbidden; '
    'production-anchor=20260825075808+77ba3a7c+2a6c96fe; '
    'credential+toolchain-blockers=recorded'
)
