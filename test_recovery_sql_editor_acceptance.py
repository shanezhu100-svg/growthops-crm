from pathlib import Path
import re

root = Path(__file__).resolve().parent
canonical = (root / 'supabase/baseline/p0_cloud_recovery_acceptance.sql').read_text(encoding='utf-8')
editor = (root / 'supabase/baseline/p0_cloud_recovery_acceptance_sql_editor.sql').read_text(encoding='utf-8')
postcheck = (root / 'supabase/baseline/p0_cloud_recovery_acceptance_postcheck.sql').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)


psql_prefix = '\\set ON_ERROR_STOP on\n\n'
editor_prefix = (
    '-- Supabase SQL Editor-compatible derivative of p0_cloud_recovery_acceptance.sql.\n'
    '-- Do not edit the acceptance body independently; canonical Gate enforces equivalence.\n'
    '-- Run only against the named empty disposable recovery target, never Production.\n\n'
)
success_tail = "\nSELECT 'P0_CLOUD_RECOVERY_ACCEPTANCE_OK'::text AS recovery_acceptance;\n"

require(canonical.startswith(psql_prefix),
        'Canonical recovery acceptance must retain the psql ON_ERROR_STOP boundary')
require(editor.startswith(editor_prefix),
        'SQL Editor recovery acceptance missing protected compatibility header')
require(editor.endswith(success_tail),
        'SQL Editor recovery acceptance must emit one explicit success row after rollback')

expected_body = canonical[len(psql_prefix):].rstrip()
editor_body = editor[len(editor_prefix):-len(success_tail)].rstrip()
require(editor_body == expected_body,
        'SQL Editor acceptance body drifted from canonical psql acceptance')

for source, label in ((canonical, 'canonical'), (editor, 'SQL Editor')):
    lowered = source.lower()
    require('begin;' in lowered and 'rollback;' in lowered,
            f'{label} recovery acceptance must be transaction-contained')
    require(re.search(r'(?im)^\s*commit\s*;', source) is None,
            f'{label} recovery acceptance must never COMMIT synthetic data')
    require('P0_RECOVERY_TARGET_NOT_EMPTY' in source,
            f'{label} recovery acceptance must refuse a non-empty CRM target')
    require('P0_CLOUD_RECOVERY_ACCEPTANCE_OK' in source,
            f'{label} recovery acceptance missing success marker')

lower_postcheck = postcheck.lower()
for fragment in (
    'count(*)::bigint from public.crm_users',
    'count(*)::bigint from public.crm_workspaces',
    'count(*)::bigint from public.crm_sessions',
    'count(*)::bigint from public.crm_server_audit_logs',
    'count(*)::bigint from vault.secrets',
    'rollback_clean',
):
    require(fragment in lower_postcheck,
            f'Recovery rollback post-check missing safe count: {fragment}')

require(lower_postcheck.count('vault.secrets') == 1,
        'Recovery rollback post-check must reference Vault only once as a count')
require('vault.decrypted_secrets' not in lower_postcheck,
        'Recovery rollback post-check must never inspect decrypted Vault plaintext')
require(re.search(r'(?im)^\s*(insert|update|delete|truncate|alter|create|drop|grant|revoke)\b', postcheck) is None,
        'Recovery rollback post-check must remain read-only')
for unsafe_rpc in (
    'crm_reveal_client_secret_value_v5',
    'crm_unlock_credentials_v1',
    'crm_save_state',
    'crm_bootstrap_admin',
):
    require(unsafe_rpc not in postcheck,
            f'Recovery rollback post-check must not execute RPC: {unsafe_rpc}')

print('RECOVERY_SQL_EDITOR_ACCEPTANCE_OK: editor body == canonical body; explicit rollback success row; postcheck=count-only/read-only')
