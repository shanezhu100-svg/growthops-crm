from pathlib import Path
import re

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260824_post_p5_single_workspace_membership_invariant.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase' / 'rollback' / '20260824_post_p5_single_workspace_membership_invariant_rollback.sql').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')

constraint = 'crm_workspace_members_user_id_key'
unique_clause = 'ADD CONSTRAINT crm_workspace_members_user_id_key UNIQUE (user_id)'
drop_clause = 'DROP CONSTRAINT crm_workspace_members_user_id_key'

if migration.count(unique_clause) != 1:
    raise SystemExit(f'Membership invariant migration must add the unique constraint exactly once: {migration.count(unique_clause)}')
if rollback.count(drop_clause) != 1:
    raise SystemExit(f'Membership invariant rollback must drop the constraint exactly once: {rollback.count(drop_clause)}')
if drop_clause in migration:
    raise SystemExit('Forward membership invariant migration must not drop the constraint')
if unique_clause in rollback:
    raise SystemExit('Membership invariant rollback must not add the constraint')

for text, label in ((migration, 'migration'), (rollback, 'rollback')):
    if text.count(constraint) < 2:
        raise SystemExit(f'{label} lost named-constraint pre/post checks')
    if 'GROUP BY user_id HAVING count(*) > 1' not in text:
        raise SystemExit(f'{label} lost duplicate-membership guard')

# Scope must remain a pure membership-table constraint change. No function,
# relation ACL, RLS, data mutation, or unrelated DDL is allowed in this migration.
body = re.sub(r'--[^\n]*', '', migration)
for forbidden in (
    r'(?im)^\s*(create|replace)\s+function\b',
    r'(?im)^\s*(grant|revoke)\b',
    r'(?im)^\s*(insert|update|delete|truncate)\b',
    r'(?im)^\s*alter\s+table\s+(?!public\.crm_workspace_members\b)',
    r'(?im)^\s*(drop|create)\s+table\b',
    r'(?im)^\s*alter\s+table\s+public\.crm_workspace_members\s+(enable|disable|force|no\s+force)\s+row\s+level\s+security\b',
):
    if re.search(forbidden, body):
        raise SystemExit(f'Unexpected migration scope matched: {forbidden}')

if build.count('python3 test_post_p5_single_workspace_membership_invariant.py') != 1:
    raise SystemExit('Canonical build must run membership invariant gate exactly once')

print('POST_P5_SINGLE_WORKSPACE_MEMBERSHIP_INVARIANT_OK: unique-user-membership=required; duplicate-preflight=required; rollback=exact; scope=constraint-only')
