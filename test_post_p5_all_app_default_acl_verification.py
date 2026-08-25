from pathlib import Path
import re

root = Path(__file__).resolve().parent
postcheck = (root / 'supabase' / 'baseline' / 'post_p5_public_default_privilege_guard_check.sql').read_text(encoding='utf-8')
probe = (root / 'supabase' / 'baseline' / 'post_p5_public_default_privilege_guard_probe.sql').read_text(encoding='utf-8')
migration = (root / 'supabase' / 'migrations' / '20260824_post_p5_public_default_privilege_guard.sql').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def strip_comments(text):
    return re.sub(r'--[^\n]*', '', text)


# This is a verification-only strengthening. The accepted migration remains the
# same reviewed Production DDL package; do not silently broaden it here.
require('revoke all privileges on tables from service_role' in migration.lower(),
        'accepted migration table default revoke drifted')
require('revoke all privileges on sequences from service_role' in migration.lower(),
        'accepted migration sequence default revoke drifted')
require('revoke execute on functions from service_role' in migration.lower(),
        'accepted migration function default revoke drifted')

# Read-only post-check must detect explicit defaults to PUBLIC as well as all
# three application roles. PUBLIC matters because effective privileges inherit it.
post_body = strip_comments(postcheck)
require(not re.search(
    r'(?im)^\s*(grant|revoke|create|alter|drop|insert|update|delete|truncate|do|begin|commit|rollback)\b',
    post_body
), 'all-app default ACL post-check must remain read-only')
for marker in (
    'table_default_app_or_public_grants',
    'sequence_default_app_or_public_grants',
    'function_default_app_or_public_grants',
    "grantee in ('PUBLIC','anon','authenticated','service_role')",
):
    require(marker in postcheck, f'post-check missing all-app default ACL marker: {marker}')

# Probe must stay transaction-contained and evaluate table/sequence effective
# privileges for anon, authenticated, and service_role. has_*_privilege also
# catches privileges inherited through PUBLIC.
probe_body = strip_comments(probe)
require(len(re.findall(r'(?im)^\s*begin\s*;', probe_body)) == 1,
        'all-app probe must start exactly one transaction')
require(len(re.findall(r'(?im)^\s*rollback\s*;', probe_body)) == 1,
        'all-app probe must roll back exactly once')
require(not re.search(r'(?im)^\s*commit\b', probe_body),
        'all-app probe must never COMMIT')
require("array['anon','authenticated','service_role']::text[]" in probe,
        'probe must iterate every application role')
require("has_table_privilege(v_role" in probe,
        'probe must check table effective privileges per application role')
require("has_sequence_privilege(v_role" in probe,
        'probe must check sequence effective privileges per application role')
for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
    require(f"'{privilege}'" in probe, f'probe missing table privilege: {privilege}')
for privilege in ('USAGE', 'SELECT', 'UPDATE'):
    require(f"'{privilege}'" in probe, f'probe missing sequence privilege: {privilege}')
for marker in ('table_rolled_back', 'sequence_rolled_back', 'function_rolled_back'):
    require(marker in probe, f'probe missing rollback proof: {marker}')

require(build.count('python3 test_post_p5_all_app_default_acl_verification.py') == 1,
        'build must execute all-app default ACL verification exactly once')

print(
    'POST_P5_ALL_APP_DEFAULT_ACL_VERIFICATION_OK: '
    'default-acl=PUBLIC+anon+authenticated+service_role; '
    'relations=effective-all-app-roles; probe=transactional-rollback; '
    'production-ddl=unchanged'
)
