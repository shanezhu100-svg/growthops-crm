from pathlib import Path
import re

root = Path(__file__).resolve().parent
workflow = (root / '.github/workflows/recovery-schema-bundle-v3.yml').read_text(encoding='utf-8')
security_sql = (root / 'supabase/baseline/recovery_post_schema_security.sql').read_text(encoding='utf-8')
allowlist_text = (root / 'supabase/baseline/recovery_service_role_rpc_allowlist.txt').read_text(encoding='utf-8')
full_export = (root / 'docs/cloudflare-migration/FULL_SCHEMA_EXPORT.md').read_text(encoding='utf-8')
current_recovery = (root / 'docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)


production_ref = 'avahcwyxparbcjdfglzx'
expected_head = '20260825075808|post_p5_rate_limit_concurrency'
expected_rpcs = tuple(
    line.strip().replace(' ', '')
    for line in allowlist_text.splitlines()
    if line.strip()
)
require(len(expected_rpcs) == 12, 'Recovery v3 RPC allowlist must contain exactly 12 entries')
require(len(set(expected_rpcs)) == 12, 'Recovery v3 RPC allowlist must not contain duplicates')

# Workflow target, data-safety and reproducibility boundaries.
for fragment in (
    'name: Recovery Schema Bundle v3',
    'workflow_dispatch:',
    "inputs.confirm_project_ref == 'avahcwyxparbcjdfglzx'",
    'SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}',
    'echo "::add-mask::${SUPABASE_DB_URL}"',
    'version: 2.116.0',
    'supabase db dump --db-url "${SUPABASE_DB_URL}" -f schema.sql',
    "EXPECTED_MIGRATION_COUNT: '51'",
    "EXPECTED_MIGRATION_HEAD: '20260825075808|post_p5_rate_limit_concurrency'",
    'event-trigger-inventory.txt',
    'event-triggers.sql',
    'post-schema-security.sql',
    'post-schema-security-origin.txt',
    'service-role-rpc-origin.txt',
    'recovery-files.sha256',
    'bundle_version=3',
    'service_role_rpc_count=12',
    'contains_customer_rows=false',
    'contains_migration_statement_arrays=false',
    'touches_supabase_admin_defaults=false',
    'empty_target_restore_required=true',
    'growthops-schema-recovery-bundle-v3-${{ github.run_id }}',
    'retention-days: 7',
):
    require(fragment in workflow, f'Recovery Bundle v3 workflow missing required control: {fragment}')

require(production_ref in workflow, 'Recovery Bundle v3 must remain pinned to canonical Production ref')
require(expected_head in workflow, 'Recovery Bundle v3 missing accepted migration head')
require('--data-only' not in workflow, 'Recovery Bundle v3 must not export Production customer rows')
require('vault.decrypted_secrets' not in workflow.lower(), 'Recovery Bundle v3 must not read Vault plaintext')
require('select statements' not in workflow.lower() and 'select rollback' not in workflow.lower(),
        'Recovery Bundle v3 must not export historical migration statement/rollback arrays')
require('diff -u supabase/baseline/recovery_service_role_rpc_allowlist.txt service-role-rpc-origin.txt' in workflow,
        'Recovery Bundle v3 must fail closed if live Production RPC allowlist drifts')
for origin_line in (
    'crm_exec|anon|0',
    'crm_exec|authenticated|0',
    'crm_exec|service_role|12',
    'crm_relation_grants|0',
    'crm_sequence_app_grants|0',
    'postgres_public_default_app_or_public_grants|0',
):
    require(origin_line in workflow, f'Recovery Bundle v3 missing Production security-origin assertion: {origin_line}')

# The post-schema security adjunct may only reconcile postgres-owned public objects
# and postgres/public defaults. It must never mutate supabase_admin defaults.
normalized_security = re.sub(r'\s+', ' ', security_sql.lower())
require('alter default privileges for role postgres in schema public' in normalized_security,
        'Recovery post-schema security must reconcile postgres/public defaults')
require(normalized_security.count('alter default privileges for role postgres in schema public') == 3,
        'Recovery post-schema security must have exactly table/sequence/function postgres default-ACL controls')
require('alter default privileges for role supabase_admin' not in normalized_security,
        'Recovery post-schema security must never alter supabase_admin defaults')
require('for role supabase_admin' not in normalized_security,
        'Recovery post-schema security must not target supabase_admin')
require("pg_get_userbyid(c.relowner) = 'postgres'" in security_sql,
        'Recovery relation reconciliation must be restricted to postgres-owned objects')
require("pg_get_userbyid(p.proowner) = 'postgres'" in security_sql,
        'Recovery function reconciliation must be restricted to postgres-owned objects')
require("c.relkind in ('r','p','v','m','f')" in security_sql,
        'Recovery post-schema security missing postgres-owned relation reconciliation')
require("c.relkind = 'S'" in security_sql,
        'Recovery post-schema security missing postgres-owned sequence reconciliation')
require('revoke all privileges on table %I.%I from anon, authenticated, service_role' in security_sql,
        'Recovery post-schema security must remove existing application-role relation privileges')
require('revoke all privileges on sequence %I.%I from anon, authenticated, service_role' in security_sql,
        'Recovery post-schema security must remove existing application-role sequence privileges')
require('revoke execute on function %I.%I(%s) from public, anon, authenticated, service_role' in security_sql,
        'Recovery post-schema security must remove existing public/application-role function EXECUTE')

# Only service_role receives an explicit recovery grant, and only for the frozen 12 RPCs.
grant_pattern = re.compile(
    r'^grant execute on function public\.([a-z0-9_]+)\(([^)]*)\) to service_role;$',
    re.MULTILINE,
)
script_rpcs = tuple(
    f'{name}|{args}'.replace(' ', '')
    for name, args in grant_pattern.findall(security_sql)
)
require(len(script_rpcs) == 12, 'Recovery post-schema security must grant exactly 12 service_role RPCs')
require(set(script_rpcs) == set(expected_rpcs),
        'Recovery post-schema security RPC grants must exactly match the frozen allowlist')
require(re.search(r'(?im)^\s*grant\b.*\b(?:anon|authenticated)\b', security_sql) is None,
        'Recovery post-schema security must never grant privileges to browser roles')
require('begin;' in security_sql.lower() and 'commit;' in security_sql.lower(),
        'Recovery post-schema security must be transaction-delimited')
require(re.search(r'(?im)^\s*(insert|update|delete|truncate)\b', security_sql) is None,
        'Recovery post-schema security must not mutate application/customer rows')

# Current recovery authorities must encode the v3 discovery and exact restore order.
for source, label in ((full_export, 'FULL_SCHEMA_EXPORT'), (current_recovery, 'CURRENT_RECOVERY_VERIFICATION')):
    require('Recovery Bundle v3' in source, f'{label} must name Recovery Bundle v3')
    require('post-schema-security.sql' in source, f'{label} must include post-schema-security.sql')
    require('default ACL' in source or 'default-ACL' in source, f'{label} must document the fresh-project default-ACL gap')
    require('schema.sql' in source and 'event-triggers.sql' in source and 'migration-ledger.sql' in source,
            f'{label} must retain complete restore components')

order_text = current_recovery.replace('`', '')
positions = [
    order_text.find('schema.sql'),
    order_text.find('event-triggers.sql', order_text.find('schema.sql') + 1),
    order_text.find('post-schema-security.sql', order_text.find('event-triggers.sql') + 1),
    order_text.find('migration-ledger.sql', order_text.find('post-schema-security.sql') + 1),
]
require(all(p >= 0 for p in positions) and positions == sorted(positions),
        'CURRENT_RECOVERY_VERIFICATION must document restore order schema -> event triggers -> post-schema security -> migration ledger')

print(
    'RECOVERY_BUNDLE_V3_OK: schema+event-triggers+post-schema-security+safe-ledger; '
    'postgres-public-defaults=fail-closed; service-role-rpc=12; supabase-admin-defaults=untouched'
)
