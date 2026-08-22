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
    require("'crm_login_v3'" not in public, f'{label}: login incorrectly merged into generic public set')
    require("'crm_public_status'" not in login, f'{label}: public status incorrectly merged into login set')
    for rpc in ('crm_login_v3', 'crm_public_status'):
        require(f"'{rpc}'" not in auth, f'{label}: {rpc} incorrectly requires an existing Session')

    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity requirement missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable-key fallback reintroduced')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin boundary missing')
    require('delete args.p_token' in source,
            f'{label}: public/login p_token stripping missing')
    require('stripSessionToken' in source,
            f'{label}: response token stripping helper missing')
    require('__Host-growthops_crm' in source and 'HttpOnly; Secure; SameSite=Strict' in source,
            f'{label}: secure login cookie contract missing')
    require('LOGIN_SESSION_MISSING' in source and 'LOGIN_FAILED' in source,
            f'{label}: generic login failure/session-missing handling weakened')

# Existing executable API tests must keep proving that login does not trust an
# incoming p_token and that the upstream token is converted into an HttpOnly cookie.
require("rpc: 'crm_login_v3'" in http_test, 'HttpOnly test lost login coverage')
require("p_token: 'browser-injected'" in http_test, 'HttpOnly test lost forged login p_token')
require("request.body.p_token, undefined" in http_test, 'HttpOnly test lost login p_token stripping proof')
require("json.token, undefined" in http_test, 'HttpOnly test lost login JSON token stripping proof')
require("__Host-growthops_crm=server-secret-token" in http_test,
        'HttpOnly test lost login cookie issuance proof')
require("rpc:'crm_login_v3'" in p2b and "data?.error" in vercel and "data?.error" in cloudflare,
        'cross-platform login path or generic error handling missing')

# Preserve repository-side internal-login controls. The live preflight also
# checks the current deployed function source before any future privilege change.
for needle in (
    'extensions.crypt',
    "action='login_failure'",
    "action='login_throttled'",
    "interval '10 minutes'",
    'v_pair_failures >= 12',
    'v_source_failures >= 50',
    'extensions.digest',
    'gen_random_bytes(32)',
    'crm_token_hash',
    'crm_role_view_state',
):
    require(needle in login_sql, f'login protection missing from migration source: {needle}')
require('raw ip' in login_sql and 'password, token, 2fa' in login_sql,
        'login migration lost no-sensitive-audit contract')

# The Group 6 live preflight itself must remain read-only and must cover all
# three relevant database functions plus the minimal public-status output.
low_preflight = preflight.lower()
require("p.proname in ('crm_login','crm_login_v3','crm_public_status')" in low_preflight,
        'Group 6 preflight lost exact function scope')
require("'internal_login_service_only'" in low_preflight,
        'Group 6 preflight lost service-only internal login check')
require("'login_wrapper_current_pre_revoke_shape'" in low_preflight and
        "'public_status_current_pre_revoke_shape'" in low_preflight,
        'Group 6 preflight lost current anon privilege checks')
require("'public_status_minimal_shape'" in low_preflight,
        'Group 6 preflight lost minimal public-status shape check')
for forbidden in ('insert ', 'update ', 'delete ', 'create ', 'alter ', 'drop ', 'grant ', 'truncate '):
    require(forbidden not in low_preflight, f'Group 6 preflight is not read-only: {forbidden.strip()}')

# Preparation-only guard: no Group 6 forward/rollback SQL may exist yet.
for folder in (root / 'supabase' / 'migrations', root / 'supabase' / 'rollback'):
    for path in folder.glob('*'):
        lowered = path.name.lower()
        require(not ('p5' in lowered and 'group6' in lowered),
                f'Group 6 SQL appeared during preparation stage: {path.name}')

require('No Group 6 forward `REVOKE` migration is included yet.' in doc,
        'Group 6 doc lost no-forward-migration guard')
require('No Group 6 rollback migration is included yet.' in doc,
        'Group 6 doc lost no-rollback guard')
require('must not advance ahead of Groups 1–5' in doc,
        'Group 6 doc lost predecessor-chain gate')
require('expected anon-executable CRM RPC count immediately before Group 6 is 2' in doc,
        'Group 6 doc lost expected final privilege transition')

print(
    'P5_GROUP6_PUBLIC_BOUNDARY_CANDIDATE_OK: '
    'public-status=no-session-public; login=no-session-cookie-bridge; '
    'server-identity=required; login-guards=preserved; preflight=read-only; production-change=none'
)
