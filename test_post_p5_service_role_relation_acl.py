from pathlib import Path

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260823_post_p5_revoke_service_role_relation_acl.sql').read_text(encoding='utf-8').lower()
rollback = (root / 'supabase' / 'rollback' / '20260823_post_p5_restore_service_role_relation_acl.sql').read_text(encoding='utf-8').lower()
preflight = (root / 'supabase' / 'baseline' / 'post_p5_service_role_relation_acl_preflight.sql').read_text(encoding='utf-8').lower()
postcheck = (root / 'supabase' / 'baseline' / 'post_p5_service_role_relation_acl_check.sql').read_text(encoding='utf-8').lower()
doc = (root / 'docs' / 'cloudflare-migration' / 'POST_P5_SERVICE_ROLE_RELATION_ACL.md').read_text(encoding='utf-8')
vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')

tables = [
    'crm_credential_unlocks',
    'crm_server_audit_logs',
    'crm_sessions',
    'crm_setup_guard',
    'crm_users',
    'crm_workspace_members',
    'crm_workspace_secret_vault',
    'crm_workspace_state',
    'crm_workspaces',
]


def require(ok, msg):
    if not ok:
        raise SystemExit(msg)


for table in tables:
    require(
        f'revoke all privileges on table public.{table} from service_role;' in migration,
        f'missing exact service_role table revoke: {table}',
    )
    require(
        f'grant select, insert, update, delete, truncate, references, trigger on table public.{table} to service_role;' in rollback,
        f'missing exact service_role table rollback: {table}',
    )

require(migration.count('revoke all privileges on table public.crm_') == 9,
        'forward migration must contain exactly nine CRM table revokes')
require('revoke all privileges on sequence public.crm_server_audit_logs_id_seq from service_role;' in migration,
        'forward migration missing audit-sequence revoke')
require('grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to service_role;' in rollback,
        'rollback missing exact audit-sequence grant')
require(' anon' not in migration and ' authenticated' not in migration,
        'forward migration must not alter browser-role privileges')
require('alter default privileges' not in migration,
        'forward migration must not alter project-level default privileges')

for sql, label in ((preflight, 'preflight'), (postcheck, 'post-check')):
    require('service_table_grant_rows' in sql, f'{label} lost table-grant count')
    require('crm_server_audit_logs_id_seq' in sql, f'{label} lost sequence ACL check')
    for forbidden in ('revoke ', 'grant ', 'alter ', 'drop ', 'truncate ', 'delete from ', 'update public.', 'insert into '):
        require(forbidden not in sql, f'{label} is no longer read-only: {forbidden.strip()}')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    require('/rest/v1/rpc/' in source, f'{label} lost RPC-only upstream path')
    require('crm_workspace_secret_vault' not in source and 'crm_users?' not in source,
            f'{label} introduced a direct CRM table endpoint')

for expected, label in (
    ('615d2c966a89d093b62492879b28cd86423ae684', 'accepted predecessor main'),
    ('20260823120150 / post_p5_minimize_service_role_rpc_exec', 'accepted predecessor migration'),
    ('258 / 625be29b82c3dfac4282313c4c32558ed3d1acebf878325959cad97fc8dc6691', 'pre-change canonical'),
    ('20260823123328 / post_p5_revoke_service_role_relation_acl', 'applied Production migration'),
    ('195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b', 'verified post-change canonical'),
    ('63 -> 0', 'table-grant transition'),
    ('3 -> 0', 'sequence-privilege transition'),
    ('preserved RPC permission-denied count: 0', 'post-apply wrapper smoke'),
):
    require(expected in doc, f'doc missing {label}')

require(build.count('python3 test_post_p5_service_role_relation_acl.py') == 1,
        'build must run relation-ACL gate exactly once')

print(
    'POST_P5_SERVICE_ROLE_RELATION_ACL_OK: '
    'tables=9x7-service-role-direct-revoke; sequence=3-direct-revoke; '
    'rpc-entry=security-definer-preserved; direct-relation=42501; '
    'service-table-grants=0; service-sequence=0; fingerprint=edfcd23e; '
    'production-change=applied+verified'
)
