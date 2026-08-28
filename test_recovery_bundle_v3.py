from pathlib import Path
import re

root = Path(__file__).resolve().parent
workflow = (root / '.github/workflows/recovery-schema-bundle-v3.yml').read_text(encoding='utf-8')
security_sql = (root / 'supabase/baseline/recovery_post_schema_security.sql').read_text(encoding='utf-8')
allowlist_text = (root / 'supabase/baseline/recovery_service_role_rpc_allowlist.txt').read_text(encoding='utf-8')
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
v3_doc = (root / 'docs/cloudflare-migration/RECOVERY_BUNDLE_V3.md').read_text(encoding='utf-8')
fresh_restore = (root / 'docs/cloudflare-migration/FRESH_V3_HOSTED_RESTORE_20260827.md').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)


expected_rpcs = tuple(line.strip().replace(' ', '') for line in allowlist_text.splitlines() if line.strip())
require(len(expected_rpcs) == 12 and len(set(expected_rpcs)) == 12,
        'Recovery v3 RPC allowlist must contain exactly 12 unique entries')

for fragment in (
    'name: Recovery Schema Bundle v3', 'workflow_dispatch:',
    "inputs.confirm_project_ref == 'avahcwyxparbcjdfglzx'",
    'SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}', 'echo "::add-mask::${SUPABASE_DB_URL}"',
    'version: 2.116.0', 'supabase db dump --db-url "${SUPABASE_DB_URL}" -f schema.sql',
    "EXPECTED_MIGRATION_COUNT: '51'", "EXPECTED_MIGRATION_HEAD: '20260825075808|post_p5_rate_limit_concurrency'",
    'event-trigger-inventory.txt', 'event-triggers.sql', 'post-schema-security.sql',
    'post-schema-security-origin.txt', 'service-role-rpc-origin.txt', 'recovery-files.sha256',
    'bundle_version=3', 'service_role_rpc_count=12', 'contains_customer_rows=false',
    'contains_migration_statement_arrays=false', 'touches_supabase_admin_defaults=false',
    'empty_target_restore_required=true', 'growthops-schema-recovery-bundle-v3-${{ github.run_id }}',
    'retention-days: 7',
):
    require(fragment in workflow, f'Recovery Bundle v3 workflow missing control: {fragment}')

require('--data-only' not in workflow and 'vault.decrypted_secrets' not in workflow.lower(),
        'Recovery Bundle v3 must exclude customer rows and Vault plaintext')
require('select statements' not in workflow.lower() and 'select rollback' not in workflow.lower(),
        'Recovery Bundle v3 must not export historical statement/rollback arrays')
require('diff -u supabase/baseline/recovery_service_role_rpc_allowlist.txt service-role-rpc-origin.txt' in workflow,
        'Recovery Bundle v3 must fail closed on live Production RPC drift')
for origin_line in (
    'crm_exec|anon|0', 'crm_exec|authenticated|0', 'crm_exec|service_role|12',
    'crm_relation_grants|0', 'crm_sequence_app_grants|0',
    'postgres_public_default_app_or_public_grants|0',
):
    require(origin_line in workflow, f'Missing Production security-origin assertion: {origin_line}')

normalized_security = re.sub(r'\s+', ' ', security_sql.lower())
require(normalized_security.count('alter default privileges for role postgres in schema public') == 3,
        'Post-schema security must have exactly postgres table/sequence/function default-ACL controls')
require('alter default privileges for role supabase_admin' not in normalized_security and
        'for role supabase_admin' not in normalized_security,
        'Post-schema security must never target supabase_admin defaults')
require("pg_get_userbyid(c.relowner) = 'postgres'" in security_sql and
        "pg_get_userbyid(p.proowner) = 'postgres'" in security_sql,
        'Existing-object reconciliation must be postgres-owned only')
for fragment in (
    "c.relkind in ('r','p','v','m','f')", "c.relkind = 'S'",
    'revoke all privileges on table %I.%I from anon, authenticated, service_role',
    'revoke all privileges on sequence %I.%I from anon, authenticated, service_role',
    'revoke execute on function %I.%I(%s) from public, anon, authenticated, service_role',
):
    require(fragment in security_sql, f'Post-schema security missing control: {fragment}')

grant_pattern = re.compile(r'^grant execute on function public\.([a-z0-9_]+)\(([^)]*)\) to service_role;$', re.MULTILINE)
script_rpcs = tuple(f'{name}|{args}'.replace(' ', '') for name, args in grant_pattern.findall(security_sql))
require(len(script_rpcs) == 12 and set(script_rpcs) == set(expected_rpcs),
        'Post-schema security service_role grants must exactly match 12-RPC allowlist')
require(re.search(r'(?im)^\s*grant\b.*\b(?:anon|authenticated)\b', security_sql) is None,
        'Post-schema security must never grant browser-role privileges')
require('begin;' in security_sql.lower() and 'commit;' in security_sql.lower(),
        'Post-schema security must be transaction-delimited')
require(re.search(r'(?im)^\s*(insert|update|delete|truncate)\b', security_sql) is None,
        'Post-schema security must not mutate application/customer rows')

for source, label in ((full_export, 'FULL_SCHEMA_EXPORT'), (v3_doc, 'RECOVERY_BUNDLE_V3')):
    for fragment in ('Recovery Bundle v3', 'post-schema-security.sql', 'schema.sql', 'event-triggers.sql', 'migration-ledger.sql'):
        require(fragment in source, f'{label} missing authority: {fragment}')
    require('default ACL' in source or 'default-ACL' in source,
            f'{label} must document fresh-project default-ACL gap')

order_text = v3_doc.replace('`', '')
ordered = order_text[order_text.find('Required restore order'):]
positions = [ordered.find(x) for x in ('schema.sql', 'event-triggers.sql', 'post-schema-security.sql', 'migration-ledger.sql')]
require(all(p >= 0 for p in positions) and positions == sorted(positions),
        'Recovery v3 restore order must be schema -> event triggers -> post-schema security -> migration ledger')

# Pin the accepted v3 artifact so current recovery authority cannot silently drift
# to an unreviewed bundle/run.
for fragment in (
    '33079493119',
    '89e1904a521c41ab1b35eb29ef25c2834bf76538',
    'growthops-schema-recovery-bundle-v3-33079493119',
    '9649406110',
    'c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7',
    '22424',
    '100993',
    '37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2',
    'd811cfa142e2268b4ef4746f7bc87f837cc21b590b3716a3f834b68b36abbfe0',
):
    require(fragment in v3_doc, f'Recovery v3 authority missing accepted artifact evidence: {fragment}')
require('artifact file count: `12`' in v3_doc,
        'Recovery v3 authority must pin accepted artifact file count')
require('exactly four `CREATE EVENT TRIGGER` statements' in v3_doc,
        'Recovery v3 authority must pin event-trigger count')
require('exactly 12 explicit CRM `service_role EXECUTE` grants' in v3_doc,
        'Recovery v3 authority must pin service_role RPC count')
require('every file listed in `recovery-files.sha256` independently verified `OK`' in v3_doc,
        'Recovery v3 authority must record checksum-manifest verification')
require('integrity and scope of the v3 artifact' in v3_doc,
        'Recovery v3 authority must distinguish artifact acceptance from #93 closure')

# Pin the second truly fresh hosted restore evidence separately from the artifact
# acceptance so an executor issue cannot be mistaken for a bundle mutation.
for fragment in (
    'qczkskuaszlezlcxxpqk',
    'growthops-recovery-bundle-v3-test',
    'public tables: `0`',
    'public routines: `0`',
    'public event triggers: `0`',
    'application migration table: absent',
    '200 / 77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65',
    '9 / 2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140',
    '225 / a0078c5da6c5844a6d02c96e5c486d3fd8b13bb859a640073fb13cbacc6032ab',
    'exactly `51` entries',
    'CRM RLS: `9 / 9`',
    '0 / 0 / 12',
    'expected database-level event triggers: `4`',
    'future-object probe',
    'crm_users = 0',
    'crm_workspaces = 0',
    'crm_sessions = 0',
    'crm_server_audit_logs = 0',
    'vault.secrets = 0',
):
    require(fragment in fresh_restore, f'Fresh v3 hosted restore evidence missing: {fragment}')

for trigger_name in (
    'ensure_rls',
    'growthops_crm_acl_guard_ddl',
    'growthops_crm_rls_guard_ddl',
    'growthops_public_noncrm_function_acl_guard_ddl',
):
    require(trigger_name in fresh_restore, f'Fresh restore evidence missing event trigger: {trigger_name}')

require('transport transcription defect' in fresh_restore and
        'did **not** contain that declaration' in fresh_restore and
        'executor transcription correction' in fresh_restore,
        'Fresh restore evidence must disclose the connector transport correction without blaming the artifact')
require('FRESH_V3_HOSTED_RESTORE_20260827.md' in v3_doc,
        'Recovery v3 authority must link the fresh hosted restore evidence')

plain_v3 = v3_doc.replace('**', '')
plain_fresh = fresh_restore.replace('**', '')
require('has not yet been executed successfully' in plain_v3,
        'Recovery v3 authority must not claim blocked full synthetic acceptance passed')
require('has not yet executed successfully' in plain_fresh,
        'Fresh restore evidence must not claim blocked full synthetic acceptance passed')
require('one substantive acceptance item' in plain_v3,
        'Recovery v3 authority must narrow #93 to the remaining synthetic acceptance')

print('RECOVERY_BUNDLE_V3_OK: artifact=33079493119/c18833d5; fresh-hosted=qczkskuaszlezlcxxpqk; fingerprints=200/9/225 accepted; synthetic-acceptance=open')
