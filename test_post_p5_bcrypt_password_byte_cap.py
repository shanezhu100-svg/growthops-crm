from pathlib import Path

migration = Path('supabase/migrations/20260824_post_p5_bcrypt_password_byte_cap.sql').read_text(encoding='utf-8')
rollback = Path('supabase/rollback/20260824_post_p5_bcrypt_password_byte_cap_rollback.sql').read_text(encoding='utf-8')
build = Path('build.sh').read_text(encoding='utf-8')

OLD = {
    'upsert': '48498837112d8cdfa65eb6ecd718d0fe',
    'bootstrap': 'abc401b6479800280b453b7346f57de6',
}
NEW = {
    'upsert': '941cd0ecb578b212851d818188e3be40',
    'bootstrap': 'ee2d5b74bb2b5fa3ed8e1b4bb214da84',
}
FUNCTIONS = {
    'upsert': 'public.crm_upsert_user(text,uuid,text,text,text,text,boolean)',
    'bootstrap': 'public.crm_bootstrap_admin(text,text,text,text)',
}
GUARD = "octet_length(coalesce(p_password,''))>72"

for label, signature in FUNCTIONS.items():
    assert signature in migration, f'migration missing {label} signature'
    assert signature in rollback, f'rollback missing {label} signature'
    assert OLD[label] in migration, f'migration missing old {label} preflight fingerprint'
    assert NEW[label] in migration, f'migration missing new {label} postcheck fingerprint'
    assert NEW[label] in rollback, f'rollback missing new {label} preflight fingerprint'
    assert OLD[label] in rollback, f'rollback missing old {label} postcheck fingerprint'

assert migration.count(GUARD) == 2, 'migration must guard both bcrypt password writers'
assert migration.count("raise exception 'PASSWORD_TOO_LONG'") == 2, 'migration must reject overlong password in both writers'
assert GUARD not in rollback, 'rollback must restore exact pre-cap function bodies'
assert "raise exception 'PASSWORD_TOO_LONG'" not in rollback, 'rollback must remove byte-cap guards'

for sql in (migration, rollback):
    for signature in FUNCTIONS.values():
        assert f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, anon, authenticated;' in sql
        assert f'GRANT EXECUTE ON FUNCTION {signature} TO service_role;' in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path TO 'public', 'extensions'" in sql

assert "python3 test_post_p5_bcrypt_password_byte_cap.py" in build
assert "node test_admin_password_input_bounds.mjs" in build

print('POST_P5_BCRYPT_PASSWORD_BYTE_CAP_OK: functions=2; bcrypt-max=72B; preflight=old-fingerprints; rollback=new-fingerprints; acl=service-role-only')
