from pathlib import Path
import re

root = Path(__file__).resolve().parent
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
current_state = (root / 'docs/cloudflare-migration/CURRENT_STATE.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')
public_recovery_doc = (root / 'docs/cloudflare-migration/PUBLIC_SCHEMA_RECOVERY_FINGERPRINT.md').read_text(encoding='utf-8')
public_recovery_sql = (root / 'supabase/baseline/p0_public_schema_recovery_fingerprint.sql').read_text(encoding='utf-8')
workflow = (root / '.github/workflows/recovery-schema-only-export.yml').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)


current_migration = '20260825075808 / post_p5_rate_limit_concurrency'
primary_hash = '77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65'
guard_hash = '2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140'
public_recovery_hash = 'a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab'
production_ref = 'avahcwyxparbcjdfglzx'
expected_event_triggers = (
    'ensure_rls',
    'growthops_crm_acl_guard_ddl',
    'growthops_crm_rls_guard_ddl',
    'growthops_public_noncrm_function_acl_guard_ddl',
)

# Current comparison anchors remain explicit across the recovery authorities.
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

# The recovery authority must now tell the truth: a real dump exists, but the
# first dump alone is not accepted as zero-to-current because database-global
# event triggers and migration history were absent from schema.sql.
require('has been produced and independently checksum-verified' in full_export,
        'FULL_SCHEMA_EXPORT must record the successful real schema export')
require('zero-to-current recovery is **not yet accepted**' in full_export,
        'FULL_SCHEMA_EXPORT must keep zero-to-current acceptance open')
require('growthops-schema-only-32983830368' in full_export,
        'FULL_SCHEMA_EXPORT missing first verified artifact authority')
require('100993' in full_export,
        'FULL_SCHEMA_EXPORT missing independently observed schema size')
require('37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2' in full_export,
        'FULL_SCHEMA_EXPORT missing verified schema SHA-256')
require('zero `CREATE EVENT TRIGGER` objects' in full_export,
        'FULL_SCHEMA_EXPORT must disclose the first-artifact event-trigger gap')
require('supabase_migrations.schema_migrations' in full_export,
        'FULL_SCHEMA_EXPORT must disclose migration-ledger portability boundary')
for trigger_name in expected_event_triggers:
    require(trigger_name in full_export,
            f'FULL_SCHEMA_EXPORT missing current event-trigger authority: {trigger_name}')
require('statements` and `rollback` arrays' in full_export,
        'FULL_SCHEMA_EXPORT must document safe migration-history minimization')
require('known 2026-08-13/14 migration-history gap remains' in full_export,
        'FULL_SCHEMA_EXPORT must preserve the unresolved historical migration-gap warning')
require('Never run the synthetic cloud recovery acceptance script against Production' in full_export,
        'FULL_SCHEMA_EXPORT must forbid synthetic acceptance on Production')
require('new, isolated, disposable Supabase project' in full_export,
        'FULL_SCHEMA_EXPORT must require a truly new recovery target')
require('Issue #93 remains open' in full_export,
        'FULL_SCHEMA_EXPORT must keep #93 open until empty-target restore acceptance')
require('A service-role/API secret is **not** a PostgreSQL database password' in full_export,
        'FULL_SCHEMA_EXPORT must forbid API-secret/DB-password substitution')

# Protected manual workflow must build the portable recovery bundle from the
# authorized Production connection without printing it or exporting customer rows.
required_workflow_fragments = (
    'workflow_dispatch:',
    "inputs.confirm_project_ref == 'avahcwyxparbcjdfglzx'",
    'SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}',
    'echo "::add-mask::${SUPABASE_DB_URL}"',
    'supabase db dump --db-url "${SUPABASE_DB_URL}" -f schema.sql',
    "EXPECTED_MIGRATION_COUNT: '51'",
    "EXPECTED_MIGRATION_HEAD: '20260825075808|post_p5_rate_limit_concurrency'",
    'supabase_migrations.schema_migrations',
    'migration-ledger.txt',
    'migration-ledger.sql',
    'event-trigger-inventory.txt',
    'event-triggers.sql',
    'from pg_event_trigger e',
    "test \"$(grep -ci '^create event trigger ' event-triggers.sql)\" = '4'",
    'recovery-files.sha256',
    'bundle_version=2',
    'contains_customer_rows=false',
    'contains_migration_statement_arrays=false',
    'empty_target_restore_required=true',
    'growthops-schema-recovery-bundle-${{ github.run_id }}',
    'retention-days: 7',
)
for fragment in required_workflow_fragments:
    require(fragment in workflow, f'recovery workflow missing required bundle control: {fragment}')

for trigger_name in expected_event_triggers:
    require(trigger_name in workflow,
            f'recovery workflow missing fail-closed expected trigger name: {trigger_name}')

require(workflow.count('supabase db dump --db-url "${SUPABASE_DB_URL}" -f schema.sql') == 1,
        'recovery workflow must generate exactly one authoritative schema.sql dump')
require('--data-only' not in workflow,
        'schema recovery workflow must not export Production customer data')
require('vault.decrypted_secrets' not in workflow.lower(),
        'schema recovery workflow must never read Vault plaintext')
require('select version, coalesce(name' in workflow,
        'recovery workflow must restrict public migration-ledger inventory to version/name')
require('statements' not in re.sub(r'contains_migration_statement_arrays=false', '', workflow),
        'recovery workflow must not select/export historical migration statement arrays')

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

sql_without_comments = '\n'.join(
    line for line in public_recovery_sql.splitlines()
    if not line.lstrip().startswith('--')
)
forbidden_statement = re.search(
    r'(?im)^\s*(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|call|do|copy)\b',
    sql_without_comments,
)
require(forbidden_statement is None,
        f'wider-public recovery fingerprint must remain read-only; found '
        f'{forbidden_statement.group(1) if forbidden_statement else "mutation"}')
require('vault.decrypted_secrets' not in public_recovery_sql.lower(),
        'wider-public recovery fingerprint must not read Vault plaintext')

require('It is **not** a schema dump' in public_recovery_doc,
        'wider-public recovery document must reject dump equivalence')
require('do not run a rollback solely because the hash changed' in public_recovery_doc,
        'wider-public recovery document must treat drift as investigation, not automatic rollback')
require('Extension version changes can legitimately change this supplemental hash' in public_recovery_doc,
        'wider-public recovery document must record extension-version drift semantics')

require(production_ref in workflow and production_ref in full_export,
        'recovery authorities must remain pinned to canonical Production ref')
require(build.count('python3 test_full_schema_export_recovery.py') == 1,
        'canonical build must execute full-schema recovery truth gate exactly once')

print(
    'FULL_SCHEMA_EXPORT_RECOVERY_OK: first-dump=verified; '
    'bundle-v2=schema+event-triggers+safe-migration-ledger; '
    'customer-data=excluded; empty-target-restore=required; '
    'production-anchor=20260825075808+77ba3a7c+2a6c96fe+a0078c5d'
)
