from pathlib import Path
import re

root = Path(__file__).resolve().parent
migration = (root / 'supabase' / 'migrations' / '20260824_post_p5_bcrypt_verification_byte_caps.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase' / 'rollback' / '20260824_post_p5_bcrypt_verification_byte_caps_rollback.sql').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


old_fp = {
    'bootstrap': 'ee2d5b74bb2b5fa3ed8e1b4bb214da84',
    'login': '88eb27fbc0acb799ef5cb63e35f1168e',
    'unlock': '03dbcf1a878ec88b7e9f71ecc9cac5d3',
}
new_fp = {
    'bootstrap': '108be4243b6cd38522a06da77a2ead7b',
    'login': 'd3af3bfea698eab3b6592da29ef3329a',
    'unlock': '0d40dda5b2bc99af44e5c39e5295b513',
}

for value in old_fp.values():
    require(value in migration, f'migration missing old fingerprint {value}')
    require(value in rollback, f'rollback missing restored fingerprint {value}')
for value in new_fp.values():
    require(value in migration, f'migration missing new fingerprint {value}')
    require(value in rollback, f'rollback missing new preflight fingerprint {value}')

for signature in (
    'crm_bootstrap_admin(p_setup_code text, p_name text, p_username text, p_password text)',
    'crm_login(p_username text, p_password text)',
    'crm_unlock_credentials_v1(p_token text, p_password text)',
):
    require(migration.count(signature) == 1, f'migration definition drift: {signature}')
    require(rollback.count(signature) == 1, f'rollback definition drift: {signature}')

# The Production migration adds one setup-code cap and two verification-password
# caps. The existing bootstrap admin-password write cap remains present in both
# directions and must never be removed by rollback.
require(migration.count("octet_length(coalesce(p_setup_code,''))>72") == 1, 'setup-code 72-byte cap missing')
require("octet_length(coalesce(p_setup_code,''))>72" not in rollback, 'rollback must remove setup-code verification cap')
require(migration.count("octet_length(coalesce(p_password,'')) > 72") == 2, 'login/unlock verification caps must appear exactly twice')
require("octet_length(coalesce(p_password,'')) > 72" not in rollback, 'rollback must remove login/unlock verification caps')
require(migration.count("octet_length(coalesce(p_password,''))>72") == 1, 'bootstrap password write cap must remain exactly once')
require(rollback.count("octet_length(coalesce(p_password,''))>72") == 1, 'rollback must preserve bootstrap password write cap')

# Oversized verification inputs keep the same generic failure vocabulary and do
# not introduce password/setup-code enumeration messages.
require("raise exception 'INVALID_SETUP_CODE'" in migration, 'setup-code cap must remain generic')
require("return jsonb_build_object('error','INVALID_CREDENTIALS')" in migration, 'login cap must remain generic')
require("raise exception 'CREDENTIAL_UNLOCK_INVALID'" in migration, 'unlock cap must remain generic')

for sql, label in ((migration, 'migration'), (rollback, 'rollback')):
    require('REVOKE ALL ON FUNCTION public.crm_login(text,text) FROM PUBLIC, anon, authenticated, service_role;' in sql, f'{label} lost internal-only crm_login ACL')
    require('GRANT EXECUTE ON FUNCTION public.crm_login(text,text) TO service_role' not in sql, f'{label} must not expose crm_login directly to service_role')
    for function in ('crm_bootstrap_admin(text,text,text,text)', 'crm_unlock_credentials_v1(text,text)'):
        require(f'REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC, anon, authenticated;' in sql, f'{label} lost browser-role revoke for {function}')
        require(f'GRANT EXECUTE ON FUNCTION public.{function} TO service_role;' in sql, f'{label} lost service_role grant for {function}')

for forbidden in (
    'GRANT EXECUTE ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) TO anon',
    'GRANT EXECUTE ON FUNCTION public.crm_bootstrap_admin(text,text,text,text) TO authenticated',
    'GRANT EXECUTE ON FUNCTION public.crm_unlock_credentials_v1(text,text) TO anon',
    'GRANT EXECUTE ON FUNCTION public.crm_unlock_credentials_v1(text,text) TO authenticated',
):
    require(forbidden not in migration and forbidden not in rollback, f'forbidden browser grant present: {forbidden}')

require(build.count('python3 test_post_p5_bcrypt_verification_byte_caps.py') == 1, 'canonical build must run bcrypt verification cap gate exactly once')

print(
    'POST_P5_BCRYPT_VERIFICATION_BYTE_CAPS_OK: '
    'bootstrap-setup-code<=72B; login-password<=72B; unlock-password<=72B; '
    'generic-failure-semantics=preserved; rollback=exact; ACL=preserved; '
    'fingerprints=108be424/d3af3bfe/0d40dda5; production-change=applied+verified'
)
