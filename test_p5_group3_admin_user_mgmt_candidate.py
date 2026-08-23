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


vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
p3p4 = (root / 'supabase' / 'baseline' / 'p3p4_attack_regression.sql').read_text(encoding='utf-8')
http_only_api_test = (root / 'test_http_only_session_api.js').read_text(encoding='utf-8')
p2b_test = (root / 'test_cloudflare_p2b_api.mjs').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE.md').read_text(encoding='utf-8')

admin_rpcs = ('crm_list_users', 'crm_upsert_user', 'crm_delete_user')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    auth = set_block(source, 'AUTH_RPCS')
    public = set_block(source, 'PUBLIC_RPCS')
    login = set_block(source, 'LOGIN_RPCS')

    for rpc in admin_rpcs:
        require(f"'{rpc}'" in auth, f'{label}: {rpc} missing from AUTH_RPCS')
        require(f"'{rpc}'" not in public, f'{label}: {rpc} leaked into PUBLIC_RPCS')
        require(f"'{rpc}'" not in login, f'{label}: {rpc} leaked into LOGIN_RPCS')

    require('__Host-growthops_crm' in source, f'{label}: HttpOnly session cookie name missing')
    require('HttpOnly; Secure; SameSite=Strict' in source, f'{label}: secure session cookie flags missing')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity requirement missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable-key fallback reintroduced')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin gate missing')
    require(('args.p_token = sessionToken' in source) or ('args.p_token=sessionToken' in source),
            f'{label}: cookie token does not overwrite browser p_token')
    require('SESSION_REQUIRED' in source, f'{label}: unauthenticated auth-RPC rejection missing')

require("'user_management_session_workspace_guards'" in p3p4,
        'P3/P4 user-management guard inventory missing')
for rpc in admin_rpcs:
    require(f"'{rpc}'" in p3p4, f'P3/P4 inventory no longer covers {rpc}')
require("src like '%crm_session_context%'" in p3p4, 'P3/P4 session-context assertion missing')
require("src like '%workspace%'" in p3p4, 'P3/P4 workspace assertion missing')
require("src like '%admin%'" in p3p4, 'P3/P4 ADMIN assertion missing')

require("p_token: 'browser-injected'" in http_only_api_test,
        'Vercel HttpOnly test no longer exercises forged p_token')
require("requestBody.p_token, 'cookie-session-token'" in http_only_api_test,
        'Vercel HttpOnly test no longer proves cookie-token overwrite')
require("'sec-fetch-site':'cross-site'" in p2b_test,
        'cross-platform P2-B test no longer checks cross-site rejection')
require("body.p_token,'cookie-session-token'" in p2b_test,
        'cross-platform P2-B test no longer proves cookie-token overwrite')
require("source.includes('GROWTHOPS_SUPABASE_SECRET_KEY')" in p2b_test,
        'cross-platform P2-B test no longer enforces secret-key identity')
for rpc in admin_rpcs:
    require(f"rpc:'{rpc}'" in p2b_test, f'cross-platform P2-B test no longer dynamically covers {rpc}')
require('admin-user-rpcs=session-gated' in p2b_test,
        'cross-platform P2-B success marker lost admin-user RPC coverage')

expected_files = (
    root / 'supabase' / 'migrations' / '20260823_p5_group3_revoke_admin_user_mgmt_anon_exec.sql',
    root / 'supabase' / 'rollback' / '20260823_p5_group3_restore_admin_user_mgmt_anon_exec.sql',
    root / 'supabase' / 'baseline' / 'p5_group3_admin_user_mgmt_anon_exec_check.sql',
    root / 'test_p5_group3_admin_user_mgmt_revocation.py',
)
for path in expected_files:
    require(path.exists(), f'Group 3 execution-package file missing: {path.name}')

# Predecessor baseline and final Group 3 Production evidence must both remain frozen.
require('92e7ed7ed6fadbbe2ba1ff5a5e029715a323964b' in doc,
        'Group 3 doc missing accepted Group2 main SHA')
require('258 / 03efe21f9345b9d01a362873b0eaf63834ab641dd0e7c8eee2ab6efa80607224' in doc,
        'Group 3 doc missing accepted Group2 fingerprint')
require('803ae738d059071b0f906732af2e45a257e8ec63' in doc,
        'Group 3 doc missing execution-package exact head')
require('dpl_A57fwk1g9HUyW7FTn9LTeXFiANVG' in doc,
        'Group 3 doc missing Vercel execution-package evidence')
require('5e9ddffb-582b-4d7c-b514-1ca3e8e8fba6' in doc,
        'Group 3 doc missing Cloudflare execution-package evidence')
require('20260823064535 / p5_group3_revoke_admin_user_mgmt_anon_exec' in doc,
        'Group 3 doc missing applied Production migration')
require('anon EXECUTE: `6` (`9 -> 6`)' in doc,
        'Group 3 doc missing post-change anon total')
require('258 / 5d43f0f65f80f24aab35d5e60d6c66cb86166f303743a5c9274509625e0c71b3' in doc,
        'Group 3 doc missing post-Group3 fingerprint')

print(
    'P5_GROUP3_ADMIN_USER_MGMT_CANDIDATE_OK: '
    'admin-rpcs=auth-only-bff; cookie-token=authoritative; '
    'server-identity=required; db-guards=covered; '
    'group2=accepted; production-change=applied+verified'
)
