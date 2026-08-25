from pathlib import Path
import re

root = Path(__file__).resolve().parent
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
current_state = (root / 'docs/cloudflare-migration/CURRENT_STATE.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')
public_recovery_doc = (root / 'docs/cloudflare-migration/PUBLIC_SCHEMA_RECOVERY_FINGERPRINT.md').read_text(encoding='utf-8')
public_recovery_sql = (root / 'supabase/baseline/p0_public_schema_recovery_fingerprint.sql').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

current_migration = '20260825075808 / post_p5_rate_limit_concurrency'
primary_hash = '77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65'
guard_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'
public_recovery_hash = 'a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab'

for source, label in (
    (full_export, 'FULL_SCHEMA_EXPORT'),
    (current_state, 'CURRENT_STATE'),
    (current_recovery, 'CURRENT_RECOVERY_VERIFICATION'),
):
    require(current_migration in source, f'{label} missing current Production migration anchor')
    require(primary_hash in source, f'{label} missing current primary CRM fingerprint')
    require(guard_hash in source, f'{label} missing current supplemental guard fingerprint')

for source, label in (
    (full_export, 'FULL_SCHEMA_EXPORT'),
    (current_recovery, 'CURRENT_RECOVERY_VERIFICATION'),
    (public_recovery_doc, 'PUBLIC_SCHEMA_RECOVERY_FINGERPRINT'),
):
    require(public_recovery_hash in source, f'{label} missing accepted wider-public recovery fingerprint')
    require('225' in source, f'{label} missing accepted wider-public inventory-line count')

require(current_migration in public_recovery_doc,
        'PUBLIC_SCHEMA_RECOVERY_FINGERPRINT missing current Production migration anchor')
require(primary_hash in public_recovery_doc,
        'PUBLIC_SCHEMA_RECOVERY_FINGERPRINT missing primary CRM comparison anchor')
require(guard_hash in public_recovery_doc,
        'PUBLIC_SCHEMA_RECOVERY_FINGERPRINT missing three-guard comparison anchor')

require('The full schema-only export is **not yet complete**.' in full_export,
        'FULL_SCHEMA_EXPORT must remain explicitly open until a real portable dump exists')
require('supabase db dump --db-url "$SUPABASE_DB_URL" -f schema.sql' in full_export,
        'FULL_SCHEMA_EXPORT missing the authorized Supabase CLI schema-only path')
require('A service-role/API secret is **not** a PostgreSQL database password' in full_export,
        'FULL_SCHEMA_EXPORT must forbid substituting the service-role secret for a DB password')
require('a generated catalog/DDL manifest or manually reconstructed SQL' in full_export,
        'FULL_SCHEMA_EXPORT must reject catalog reconstruction as dump completion')
require('supplemental wider-public recovery fingerprint' in full_export,
        'FULL_SCHEMA_EXPORT must list the wider-public fingerprint as comparison evidence')
require('Do not mark this deliverable complete until a real export artifact has been produced' in full_export,
        'FULL_SCHEMA_EXPORT must require an actual export artifact')
require('known 2026-08-13/14 migration-history gap remains' in full_export,
        'FULL_SCHEMA_EXPORT must preserve the unresolved historical migration-gap warning')
require('no database password/credential-bearing connection string is available' in full_export,
        'FULL_SCHEMA_EXPORT must record the current credential blocker')
require('no Supabase CLI / Docker / Podman / `pg_dump` / `psql` toolchain' in full_export,
        'FULL_SCHEMA_EXPORT must record the current toolchain blocker')

# The wider-public query must stay catalog-only and emit only comparison metadata.
require('Read-only catalog inspection only' in public_recovery_sql,
        'wider-public fingerprint SQL must document its read-only boundary')
require('count(*)::bigint as inventory_lines' in public_recovery_sql,
        'wider-public fingerprint SQL must emit deterministic inventory count')
require('as public_recovery_sha256' in public_recovery_sql,
        'wider-public fingerprint SQL must emit deterministic SHA-256 only')
for required_catalog in (
    'pg_namespace',
    'pg_class',
    'information_schema.columns',
    'pg_constraint',
    'pg_indexes',
    'pg_trigger',
    'pg_proc',
    'pg_policies',
    'pg_event_trigger',
    'pg_default_acl',
    'pg_extension',
):
    require(required_catalog in public_recovery_sql,
            f'wider-public fingerprint SQL missing catalog coverage: {required_catalog}')
require("has_function_privilege('anon'" in public_recovery_sql and
        "has_function_privilege('authenticated'" in public_recovery_sql and
        "has_function_privilege('service_role'" in public_recovery_sql,
        'wider-public fingerprint SQL must retain effective application-role EXECUTE comparison')
require('pg_get_functiondef(p.oid)' in public_recovery_sql,
        'wider-public fingerprint SQL must hash public routine definitions')

sql_without_comments = '\n'.join(
    line for line in public_recovery_sql.splitlines()
    if not line.lstrip().startswith('--')
)
forbidden_statement = re.search(
    r'(?im)^\s*(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|call|do|copy)\b',
    sql_without_comments,
)
require(forbidden_statement is None,
        f'wider-public recovery fingerprint must remain read-only; found {forbidden_statement.group(1) if forbidden_statement else "mutation"}')
require('vault.decrypted_secrets' not in public_recovery_sql.lower(),
        'wider-public recovery fingerprint must not read Vault plaintext')

require('It is **not** a schema dump' in public_recovery_doc,
        'wider-public recovery document must reject dump equivalence')
require('do not run a rollback solely because the hash changed' in public_recovery_doc,
        'wider-public recovery document must treat drift as investigation, not automatic rollback')
require('Extension version changes can legitimately change this supplemental hash' in public_recovery_doc,
        'wider-public recovery document must record extension-version drift semantics')
require('full schema-only export remains open' in public_recovery_doc,
        'wider-public recovery document must keep portable dump deliverable open')

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
    'production-anchor=20260825075808+77ba3a7c+2a6c96fe+a0078c5d; '
    'wider-public=225-lines; credential+toolchain-blockers=recorded'
)
