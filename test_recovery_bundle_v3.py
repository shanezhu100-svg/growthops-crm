from pathlib import Path
import re

root = Path(__file__).resolve().parent
workflow = (root / '.github/workflows/recovery-schema-bundle-v3.yml').read_text(encoding='utf-8')
security_sql = (root / 'supabase/baseline/recovery_post_schema_security.sql').read_text(encoding='utf-8')
allowlist_text = (root / 'supabase/baseline/recovery_service_role_rpc_allowlist.txt').read_text(encoding='utf-8')
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
v3_doc = (root / 'docs/cloudflare-migration/RECOVERY_BUNDLE_V3.md').read_text(encoding='utf-8')


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
plain_v3 = v3_doc.replace('**', '')
require('has not yet been executed successfully' in plain_v3,
        'Recovery v3 authority must not claim blocked full synthetic acceptance passed')

print('RECOVERY_BUNDLE_V3_OK: postgres/public ACL reconciliation pinned; service-role RPC=12; supabase_admin untouched')
