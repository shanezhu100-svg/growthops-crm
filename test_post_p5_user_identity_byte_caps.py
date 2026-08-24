from pathlib import Path

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260824_post_p5_user_identity_byte_caps.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase' / 'rollback' / '20260824_post_p5_user_identity_byte_caps_rollback.sql').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


old_bootstrap = '108be4243b6cd38522a06da77a2ead7b'
old_upsert = '941cd0ecb578b212851d818188e3be40'
new_bootstrap = '074db868b0b66ac95fa5ef6bbe5b96c2'
new_upsert = '6a6987b7b44cb75ef7a62241cec563c5'
for value in (old_bootstrap, old_upsert, new_bootstrap, new_upsert):
    require(value in migration, f'migration missing fingerprint {value}')
    require(value in rollback, f'rollback missing fingerprint {value}')

constraints = (
    'crm_users_name_bytes_check',
    'crm_users_username_bytes_check',
    'crm_users_username_key_bytes_check',
)
for name in constraints:
    require(migration.count(name) >= 2, f'migration lost named constraint checks: {name}')
    require(rollback.count(name) >= 2, f'rollback lost named constraint checks: {name}')
require(migration.count('ADD CONSTRAINT crm_users_name_bytes_check CHECK (octet_length(name)<=256)') == 1, 'name byte cap must be exactly 256')
require(migration.count('ADD CONSTRAINT crm_users_username_bytes_check CHECK (octet_length(username)<=256)') == 1, 'username byte cap must be exactly 256')
require(migration.count('ADD CONSTRAINT crm_users_username_key_bytes_check CHECK (octet_length(username_key)<=256)') == 1, 'username_key byte cap must be exactly 256')
for name in constraints:
    require(rollback.count(f'DROP CONSTRAINT {name}') == 1, f'rollback must drop {name} exactly once')

identity_guard = "octet_length(v_name)>256 or octet_length(v_username)>256 or octet_length(lower(v_username))>256"
require(migration.count(identity_guard) == 1, 'upsert identity byte guard missing/drifted')
require(identity_guard not in rollback, 'rollback must restore pre-identity-cap upsert definition')
require(migration.count("octet_length(v_name)>256") == 2, 'forward migration must cap name in upsert + bootstrap')
require(migration.count("octet_length(v_username)>256") == 2, 'forward migration must cap username in upsert + bootstrap')
require("octet_length(v_name)>256" not in rollback, 'rollback must remove identity name guards')
require("octet_length(v_username)>256" not in rollback, 'rollback must remove identity username guards')

# Preserve prior bcrypt hardening while adding identity bounds.
for marker in (
    "octet_length(coalesce(p_setup_code,''))>72",
    "octet_length(coalesce(p_password,''))>72",
    "raise exception 'PASSWORD_TOO_LONG'",
):
    require(marker in migration and marker in rollback, f'prior bcrypt guard lost: {marker}')

for sql, label in ((migration, 'migration'), (rollback, 'rollback')):
    for function in ('crm_bootstrap_admin(text,text,text,text)', 'crm_upsert_user(text,uuid,text,text,text,text,boolean)'):
        require(f'REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC, anon, authenticated;' in sql, f'{label} lost browser revoke for {function}')
        require(f'GRANT EXECUTE ON FUNCTION public.{function} TO service_role;' in sql, f'{label} lost service_role grant for {function}')

require(build.count('python3 test_post_p5_user_identity_byte_caps.py') == 1, 'canonical build must run identity byte-cap gate exactly once')

print(
    'POST_P5_USER_IDENTITY_BYTE_CAPS_OK: '
    'name<=256B; username<=256B; username-key<=256B; table-checks=3; '
    'upsert+bootstrap=fail-fast; bcrypt-guards=preserved; rollback=exact; '
    'fingerprints=074db868/6a6987b7; production-change=applied+verified'
)
