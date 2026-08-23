from pathlib import Path
import re

root = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def sql_body(path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'--[^\n]*', '', text)
    return ' '.join(text.lower().split())


migration = sql_body(root / 'supabase' / 'migrations' / '20260823_revoke_browser_audit_sequence_acl.sql')
rollback = sql_body(root / 'supabase' / 'rollback' / '20260823_restore_browser_audit_sequence_acl.sql')
check = sql_body(root / 'supabase' / 'baseline' / 'post_p5_audit_sequence_acl_check.sql')
doc = (root / 'docs' / 'cloudflare-migration' / 'POST_P5_RESIDUAL_SEQUENCE_ACL.md').read_text(encoding='utf-8')

forward = (
    'revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from anon; '
    'revoke select, update, usage on sequence public.crm_server_audit_logs_id_seq from authenticated;'
)
reverse = (
    'grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to anon; '
    'grant select, update, usage on sequence public.crm_server_audit_logs_id_seq to authenticated;'
)

require(migration == forward, f'residual sequence migration must contain exactly two browser-role revokes: {migration!r}')
require(rollback == reverse, f'residual sequence rollback must contain exactly two inverse grants: {rollback!r}')

for forbidden in (' create ', ' alter ', ' drop ', ' insert ', ' delete ', ' truncate ', ' grant '):
    require(forbidden not in f' {migration} ', f'forbidden mutation in residual sequence migration: {forbidden.strip()}')

require('crm_server_audit_logs_id_seq' in check, 'sequence post-check lost exact target')
for role in ('public', 'anon', 'authenticated', 'service_role'):
    require(f"has_sequence_privilege('{role}'" in check, f'post-check lost {role} sequence privilege inspection')
for privilege in ('select', 'update', 'usage'):
    require(f"'{privilege}'" in check, f'post-check lost {privilege} privilege inspection')
require('total_crm_sequences' in check, 'post-check lost CRM sequence inventory count')
for forbidden in (' revoke ', ' grant ', ' create ', ' alter ', ' drop ', ' insert ', ' update ', ' delete ', ' truncate '):
    require(forbidden not in f' {check} ', f'sequence post-check is not read-only: {forbidden.strip()}')

for expected, message in (
    ('main@e132c5b9919be6d484f222e5a9dff3eba1944976', 'accepted post-P5 main SHA'),
    ('PUBLIC EXECUTE`: `0`', 'PUBLIC function boundary'),
    ('anon EXECUTE`: `0`', 'anon function boundary'),
    ('authenticated EXECUTE`: `0`', 'authenticated function boundary'),
    ('service_role EXECUTE`: `40`', 'service-role function boundary'),
    ('browser-role direct CRM table grants: `0`', 'table boundary'),
    ('258 / 40aa990fdd83bf8a132b94df0e20e4a57af607a2c032980671ba94c0c6c1a8df', 'accepted P5 fingerprint'),
    ('IDENTITY ALWAYS', 'sequence ownership relationship'),
    ('SECURITY DEFINER', 'audit writer dependency proof'),
    ('does **not** alter global `supabase_admin` defaults', 'global-default non-goal'),
    ('does not include sequence ACL rows', 'canonical fingerprint limitation'),
):
    require(expected in doc, f'residual sequence doc missing {message}')

# P5 must remain fully closed while this follow-up is prepared.
for filename, marker in (
    ('test_p5_group6_public_boundary_candidate.py', 'production-change=applied+verified'),
    ('test_p5_group6_public_boundary_revocation.py', 'expected-anon=0'),
):
    source = (root / filename).read_text(encoding='utf-8')
    require(marker in source, f'post-P5 gate lost accepted P5 marker: {marker}')

print(
    'POST_P5_AUDIT_SEQUENCE_ACL_OK: '
    'target=crm_server_audit_logs_id_seq; browser-select-update-usage=revoke; '
    'service-role=preserved; rollback=exact; post-check=read-only; p5=closed'
)
