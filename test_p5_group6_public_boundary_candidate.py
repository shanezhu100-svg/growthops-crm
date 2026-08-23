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
http_test = (root / 'test_http_only_session_api.js').read_text(encoding='utf-8')
p2b = (root / 'test_cloudflare_p2b_api.mjs').read_text(encoding='utf-8')
login_sql = (root / 'supabase' / 'migrations' / '20260815_p2_login_audit_rate_limit.sql').read_text(encoding='utf-8').lower()
preflight = (root / 'supabase' / 'baseline' / 'p5_group6_public_boundary_preflight.sql').read_text(encoding='utf-8')
doc = (root / 'docs' / 'cloudflare-migration' / 'P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE.md').read_text(encoding='utf-8')

for label, source in (('Vercel', vercel), ('Cloudflare', cloudflare)):
    public = set_block(source, 'PUBLIC_RPCS')
    login = set_block(source, 'LOGIN_RPCS')
    auth = set_block(source, 'AUTH_RPCS')
    require("'crm_public_status'" in public, f'{label}: public status missing from PUBLIC_RPCS')
    require("'crm_login_v3'" in login, f'{label}: login v3 missing from LOGIN_RPCS')
    require("'crm_login_v3'" not in public and "'crm_public_status'" not in login,
            f'{label}: public/login boundary collapsed')
    for rpc in ('crm_login_v3', 'crm_public_status'):
        require(f"'{rpc}'" not in auth, f'{label}: {rpc} incorrectly requires an existing Session')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity requirement missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable-key fallback reintroduced')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin boundary missing')
    require('delete args.p_token' in source and 'stripSessionToken' in source,
            f'{label}: public/login token boundary missing')
    require('__Host-growthops_crm' in source and 'HttpOnly; Secure; SameSite=Strict' in source,
            f'{label}: secure login cookie contract missing')
    require('LOGIN_SESSION_MISSING' in source and 'LOGIN_FAILED' in source,
            f'{label}: generic login failure/session-missing handling weakened')

require("rpc: 'crm_login_v3'" in http_test, 'HttpOnly test lost login coverage')
require("p_token: 'browser-injected'" in http_test and "request.body.p_token, undefined" in http_test,
        'HttpOnly test lost forged login p_token stripping proof')
require("json.token, undefined" in http_test and "__Host-growthops_crm=server-secret-token" in http_test,
        'HttpOnly test lost login token-to-cookie proof')
require("rpc:'crm_login_v3'" in p2b and "data?.error" in vercel and "data?.error" in cloudflare,
        'cross-platform login path or generic error handling missing')

for needle in (
    'extensions.crypt', "action='login_failure'", "action='login_throttled'",
    "interval '10 minutes'", 'v_pair_failures >= 12', 'v_source_failures >= 50',
    'extensions.digest', 'gen_random_bytes(32)', 'crm_token_hash', 'crm_role_view_state',
):
    require(needle in login_sql, f'login protection missing from migration source: {needle}')
require('raw ip' in login_sql and 'password, token, 2fa' in login_sql,
        'login migration lost no-sensitive-audit contract')

low_preflight = preflight.lower()
require("p.proname in ('crm_login','crm_login_v3','crm_public_status')" in low_preflight,
        'Group 6 preflight lost exact function scope')
for needle in ("'internal_login_service_only'", "'login_wrapper_current_pre_revoke_shape'",
               "'public_status_current_pre_revoke_shape'", "'public_status_minimal_shape'"):
    require(needle in low_preflight, f'Group 6 preflight lost check: {needle}')
for forbidden in ('insert ', 'update ', 'delete ', 'create ', 'alter ', 'drop ', 'grant ', 'truncate '):
    require(forbidden not in low_preflight, f'Group 6 preflight is not read-only: {forbidden.strip()}')

expected_files = (
    root / 'supabase' / 'migrations' / '20260823_p5_group6_revoke_public_boundary_anon_exec.sql',
    root / 'supabase' / 'rollback' / '20260823_p5_group6_restore_public_boundary_anon_exec.sql',
    root / 'supabase' / 'baseline' / 'p5_group6_public_boundary_anon_exec_check.sql',
    root / 'test_p5_group6_public_boundary_revocation.py',
)
for path in expected_files:
    require(path.exists(), f'Group 6 execution-package file missing: {path.name}')

allowed_sql = {
    '20260823_p5_group6_revoke_public_boundary_anon_exec.sql',
    '20260823_p5_group6_restore_public_boundary_anon_exec.sql',
}
for folder in (root / 'supabase' / 'migrations', root / 'supabase' / 'rollback'):
    for path in folder.glob('*'):
        lowered = path.name.lower()
        if 'p5' in lowered and 'group6' in lowered:
            require(lowered in allowed_sql, f'unexpected Group 6 SQL file: {path.name}')

for expected, message in (
    ('23b898ac6d7faaa79142e85e267ef7544a9c0b30', 'accepted Group5 main SHA'),
    ('20260823085810 / p5_group5_revoke_session_state_anon_exec', 'accepted Group5 migration'),
    ('258 / 50522a7a3029da6a81a094241e804cb540987616e0f8622dc6606e2fab39e3cb', 'accepted Group5 fingerprint'),
    ('ae9dddc184ff64a29889993ba8654ab442aa7249', 'preparation exact head'),
    ('dpl_AkEqRfjAavuDfJTh77Ty3Fve7RVK', 'Vercel preparation evidence'),
    ('8817ca84-6f20-462f-8f4f-9b9b73c17b13', 'Cloudflare preparation evidence'),
    ('7/7 PASS', 'live Production preflight evidence'),
    ('Production has not been changed by Group 6 yet.', 'pre-apply Production boundary'),
    ('anon CRM EXECUTE: `2 -> 0`', 'expected final privilege transition'),
):
    require(expected in doc, f'Group 6 doc missing {message}')

print(
    'P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE_OK: '
    'public-status=no-session-public; login=no-session-cookie-bridge; '
    'server-identity=required; login-guards=preserved; preflight=read-only; '
    'group5=accepted; package=prepared; production-change=none'
)
