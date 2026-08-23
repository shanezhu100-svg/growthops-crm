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


rpcs = ('crm_load_state_v3', 'crm_save_state', 'crm_logout')
vercel = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions' / 'api' / 'crm.js').read_text(encoding='utf-8')
p3p4 = (root / 'supabase' / 'baseline' / 'p3p4_attack_regression.sql').read_text(encoding='utf-8')
http_api = (root / 'test_http_only_session_api.js').read_text(encoding='utf-8')
p2b = (root / 'test_cloudflare_p2b_api.mjs').read_text(encoding='utf-8')
attack = (root / 'test_cloudflare_p3p4_attack_regression.mjs').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'P5_GROUP5_SESSION_STATE_CANDIDATE.md').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    auth = set_block(source, 'AUTH_RPCS')
    public = set_block(source, 'PUBLIC_RPCS')
    login = set_block(source, 'LOGIN_RPCS')
    for rpc in rpcs:
        require(f"'{rpc}'" in auth, f'{label}: {rpc} missing from AUTH_RPCS')
        require(f"'{rpc}'" not in public, f'{label}: {rpc} leaked into PUBLIC_RPCS')
        require(f"'{rpc}'" not in login, f'{label}: {rpc} leaked into LOGIN_RPCS')
    require('__Host-growthops_crm' in source, f'{label}: session cookie missing')
    require('HttpOnly; Secure; SameSite=Strict' in source, f'{label}: secure cookie flags missing')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable fallback reintroduced')
    require(('args.p_token = sessionToken' in source) or ('args.p_token=sessionToken' in source),
            f'{label}: cookie token no longer authoritative')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin gate missing')
    require('SESSION_REQUIRED' in source, f'{label}: no-session gate missing')

require("'save_state_session_and_secret_guard'" in p3p4,
        'P3/P4 save-state guard inventory missing')
require("from functions where proname='crm_save_state'" in p3p4,
        'P3/P4 no longer scopes save-state guard to crm_save_state')
require("src like '%crm_session_context%'" in p3p4 and
        "src like '%crm_redact_secrets%'" in p3p4 and
        "src like '%crm_extract_live_secrets%'" in p3p4,
        'P3/P4 save-state session/secret assertions weakened')
require("p_token: 'browser-injected'" in http_api,
        'HttpOnly API test lost forged-token exercise')
require("requestBody.p_token, 'cookie-session-token'" in http_api,
        'HttpOnly API test lost cookie-token overwrite proof')
require("rpc:'crm_load_state_v3'" in p2b,
        'cross-platform P2-B test lost state-load coverage')
require("rpc:'crm_logout'" in p2b,
        'cross-platform P2-B test lost logout coverage')
require('logout-failure' in attack and 'clears-cookie' in attack,
        'P3/P4 attack regression lost logout failure cookie-clear contract')

expected_files = (
    root / 'supabase' / 'migrations' / '20260823_p5_group5_revoke_session_state_anon_exec.sql',
    root / 'supabase' / 'rollback' / '20260823_p5_group5_restore_session_state_anon_exec.sql',
    root / 'supabase' / 'baseline' / 'p5_group5_session_state_anon_exec_check.sql',
    root / 'test_p5_group5_session_state_revocation.py',
)
for path in expected_files:
    require(path.exists(), f'Group 5 execution-package file missing: {path.name}')

allowed_sql = {
    '20260823_p5_group5_revoke_session_state_anon_exec.sql',
    '20260823_p5_group5_restore_session_state_anon_exec.sql',
}
for folder in (root / 'supabase' / 'migrations', root / 'supabase' / 'rollback'):
    for path in folder.glob('*'):
        lowered = path.name.lower()
        if 'p5' in lowered and 'group5' in lowered:
            require(lowered in allowed_sql, f'unexpected Group 5 SQL file: {path.name}')

# Freeze accepted predecessor, exact pre-apply platform evidence and verified
# Production result. Live DB assertions are performed separately before merge.
for expected, message in (
    ('385bff8e0316bf8b1460b12202ea88f8c880a2c4', 'accepted Group4 main SHA'),
    ('20260823071407 / p5_group4_revoke_safe_summary_anon_exec', 'accepted Group4 migration'),
    ('258 / c3a5ef7bdd5c5d7c347d8155224ae4cc299e80917fccc8a622096c35e6e1bf4b', 'accepted Group4 fingerprint'),
    ('1068d5ba4c603f64b34ca99c6257718e268f9e1e', 'execution-package exact head'),
    ('dpl_HWTZvqWfWW4gCGX8RjrMLwEMxPqt', 'Vercel execution-package evidence'),
    ('b5b3919a-9d3d-49a7-b2c9-b45fa2df8d05', 'Cloudflare execution-package evidence'),
    ('20260823085810 / p5_group5_revoke_session_state_anon_exec', 'applied Production migration'),
    ('258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb', 'post-Group5 canonical fingerprint'),
):
    require(expected in doc, f'Group 5 doc missing {message}')

require('anon EXECUTE: `2` (`5 -> 2`)' in doc,
        'Group 5 doc missing post-change anon total')
require('`crm_login_v3(text,text)`' in doc and '`crm_public_status()`' in doc,
        'Group 5 doc lost exact remaining anon boundary')
require('deliberately does not require `crm_session_context`' in doc,
        'Group 5 doc lost logout semantic distinction')
require('exactly three `FPRIV` transitions' in doc,
        'Group 5 doc lost expected fingerprint-delta explanation')

print(
    'P5_GROUP5_SESSION_STATE_CANDIDATE_OK: '
    'load+save+logout=auth-only-bff; cookie-token=authoritative; '
    'save-secret-guard=covered; logout-distinction=preserved; '
    'group4=accepted; production-change=applied+verified'
)
