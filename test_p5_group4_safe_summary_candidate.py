from pathlib import Path
import re

root = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def set_block(source, name):
    match = re.search(rf"const\s+{re.escape(name)}\s*=\s*new Set\(\[(.*?)\]\);", source, re.S)
    require(match is not None, f'{name} set not found')
    return match.group(1)


rpc = 'crm_client_account_safe_summary'
vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
runtime = (root / 'dist' / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
migration = (root / 'supabase' / 'migrations' / '20260816_client_account_safe_summary.sql').read_text(encoding='utf-8')
v6_test = (root / 'test_credential_ui_v6_output.py').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'P5_GROUP4_SAFE_SUMMARY_CANDIDATE.md').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    auth = set_block(source, 'AUTH_RPCS')
    public = set_block(source, 'PUBLIC_RPCS')
    login = set_block(source, 'LOGIN_RPCS')
    require(f"'{rpc}'" in auth, f'{label}: safe-summary missing from AUTH_RPCS')
    require(f"'{rpc}'" not in public, f'{label}: safe-summary leaked into PUBLIC_RPCS')
    require(f"'{rpc}'" not in login, f'{label}: safe-summary leaked into LOGIN_RPCS')
    require('__Host-growthops_crm' in source, f'{label}: session cookie boundary missing')
    require('HttpOnly; Secure; SameSite=Strict' in source, f'{label}: secure session cookie flags missing')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity requirement missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable-key fallback reintroduced')
    require(('args.p_token = sessionToken' in source) or ('args.p_token=sessionToken' in source),
            f'{label}: cookie token no longer overrides browser p_token')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin boundary missing')
    require('SESSION_REQUIRED' in source, f'{label}: missing authenticated-RPC session rejection')

require(rpc in runtime, 'final credential runtime lost safe-summary dependency')
require('crm_client_credential_status' not in runtime,
        'legacy credential-status RPC reappeared in final runtime')
require(rpc in v6_test, 'v6 output test no longer preserves safe-summary dependency')
require('crm_client_credential_status' in v6_test,
        'v6 output test no longer guards legacy credential-status retirement')

low = migration.lower()
require('security definer' in low, 'safe-summary definition no longer SECURITY DEFINER')
require('crm_session_context(p_token)' in low, 'safe-summary lost session-context guard')
require("c.role not in ('admin','ops')" in low, 'safe-summary lost ADMIN/OPS role guard')
require('crm_read_workspace_secrets(c.workspace_id)' in low,
        'safe-summary no longer workspace-scoped to Vault tree')
require('crm_reveal' not in low, 'safe-summary must never call a reveal RPC')

return_pos = low.find('return jsonb_build_object(')
require(return_pos >= 0, 'safe-summary return object not found')
return_block = low[return_pos:]
for key in ('clientid', 'facebook', 'tiktok', 'googleaccounts', 'instagramaccounts', 'loginaccount', 'haspassword', 'has2fa'):
    require(f"'{key}'" in return_block, f'safe-summary expected output key missing: {key}')
for forbidden in ("'password',", "'2fa',", "'loginpassword',", "'login_password',", "'value',"):
    require(forbidden not in return_block, f'safe-summary started returning forbidden secret field: {forbidden}')
require("'haspassword',public.crm_secret_value_nonempty" in return_block.replace(' ', ''),
        'safe-summary hasPassword is no longer a boolean presence check')
require("'has2fa'," in return_block.replace(' ', ''), 'safe-summary has2FA presence field missing')
require('password / 2fa values are never returned by this rpc' in low,
        'safe-summary migration lost explicit no-plaintext contract')

expected_files = (
    root / 'supabase' / 'migrations' / '20260823_p5_group4_revoke_safe_summary_anon_exec.sql',
    root / 'supabase' / 'rollback' / '20260823_p5_group4_restore_safe_summary_anon_exec.sql',
    root / 'supabase' / 'baseline' / 'p5_group4_safe_summary_anon_exec_check.sql',
    root / 'test_p5_group4_safe_summary_revocation.py',
)
for path in expected_files:
    require(path.exists(), f'Group 4 execution-package file missing: {path.name}')

allowed_sql = {
    '20260823_p5_group4_revoke_safe_summary_anon_exec.sql',
    '20260823_p5_group4_restore_safe_summary_anon_exec.sql',
}
for folder in (root / 'supabase' / 'migrations', root / 'supabase' / 'rollback'):
    for path in folder.glob('*'):
        lowered = path.name.lower()
        if 'p5' in lowered and 'group4' in lowered:
            require(lowered in allowed_sql, f'unexpected Group 4 SQL file: {path.name}')

# Freeze the predecessor baseline, execution-package exact-head evidence, and
# final Production acceptance evidence. These are documentation gates only;
# they do not make a live database assertion during build.
require('b78d3135f648de7f2c2abf417c0cd4f9cc2c6b89' in doc,
        'Group 4 doc missing accepted Group3 main SHA')
require('20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec' in doc,
        'Group 4 doc missing accepted Group3 migration')
require('258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3' in doc,
        'Group 4 doc missing accepted Group3 fingerprint')
require('c8ef33d2dec3993a122fd960e0e6c284a8ef51e6' in doc,
        'Group 4 doc missing execution-package exact head')
require('dpl_9WJ66t9iVaNyx9SGWZr9MWDHXbpx' in doc,
        'Group 4 doc missing Vercel execution-package evidence')
require('32b8f3be-b447-4403-a93d-1867182f68aa' in doc,
        'Group 4 doc missing Cloudflare execution-package evidence')
require('20260823071407 / p5_group4_revoke_safe_summary_anon_exec' in doc,
        'Group 4 doc missing applied Production migration')
require('anon EXECUTE: `5` (`6 -> 5`)' in doc,
        'Group 4 doc missing post-change anon total')
require('258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b' in doc,
        'Group 4 doc missing post-Group4 canonical fingerprint')
require('exactly one `FPRIV` transition' in doc,
        'Group 4 doc lost expected fingerprint-delta explanation')

print(
    'P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK: '
    'safe-summary=auth-only-bff+final-runtime; output=identifier+presence-booleans-only; '
    'reveal-call=none; group3=accepted; production-change=applied+verified'
)
