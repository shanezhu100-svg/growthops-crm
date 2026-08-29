from pathlib import Path
import re

root = Path(__file__).resolve().parent
dist = root / 'dist'
api = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')
security = (dist / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
p1 = (dist / 'cloud-p1-overrides.js').read_text(encoding='utf-8')
bridge = (dist / 'cloud-ui-action-bridge.js').read_text(encoding='utf-8')
html = (dist / 'index.html').read_text(encoding='utf-8')

required_api = (
    "const COOKIE_NAME = '__Host-growthops_crm';",
    "return `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;",
    "return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;",
    'HttpOnly; Secure; SameSite=Strict',
    "const AUTH_RPCS = new Set([",
    "'crm_load_state_v3'",
    "'crm_save_state'",
    "'crm_logout'",
    "'crm_list_users'",
    "'crm_upsert_user'",
    "'crm_delete_user'",
    "'crm_client_account_safe_summary'",
    "'crm_unlock_credentials_v1'",
    "'crm_reveal_client_secret_value_v5'",
    'if (!ALL_RPCS.has(rpc))',
    'if (!sameOrigin(req))',
    'args.p_token = sessionToken;',
    'delete safe.token;',
    "res.setHeader('Set-Cookie', sessionCookie(token));",
    "res.setHeader('Set-Cookie', clearSessionCookie());",
    "res.setHeader('Cache-Control', 'no-store, max-age=0');",
)
missing = [marker for marker in required_api if marker not in api]
if missing:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED missing API markers: ' + ', '.join(missing))

# The __Host- cookie prefix is only meaningful when the cookie is host-only,
# Secure, and scoped exactly to Path=/. Keep both Set-Cookie helpers fail-closed:
# adding Domain= or broadening/narrowing Path must break the canonical build.
for helper_name in ('sessionCookie', 'clearSessionCookie'):
    match = re.search(rf'function {helper_name}\([^)]*\) \{{(.*?)\n\}}', api, flags=re.S)
    if not match:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED missing cookie helper: ' + helper_name)
    helper = match.group(1)
    if re.search(r'\bDomain\s*=', helper, flags=re.I):
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED __Host- cookie must not set Domain')
    if helper.count('Path=/;') != 1:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED __Host- cookie must use exact Path=/')
    for marker in ('HttpOnly', 'Secure', 'SameSite=Strict'):
        if marker not in helper:
            raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED __Host- cookie missing ' + marker)

for forbidden in (
    "'crm_reveal_client_secret_field_v4'",
    "'crm_reveal_client_secret_field_v3'",
    "'crm_reveal_client_secrets'",
):
    if forbidden in api:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED broader reveal RPC allowlisted: ' + forbidden)

required_adapter = (
    "const SESSION_MARKER='cookie';",
    "const LEGACY_SESSION_KEY=['growthops','crm','token','v2'].join('_');",
    'localStorage.removeItem(LEGACY_SESSION_KEY)',
    "fetch('/api/crm'",
    "credentials:'same-origin'",
    "JSON.stringify({rpc:name,args:body})",
    "token=SESSION_MARKER;revision=Number(d?.revision||0);",
    "rpc('crm_login_v3'",
    "rpc('crm_load_state_v3'",
    "document.documentElement.classList.remove('growthops-session-restoring')",
)
missing = [marker for marker in required_adapter if marker not in adapter]
if missing:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED missing adapter markers: ' + ', '.join(missing))

for name, text in (
    ('cloud-adapter.js', adapter),
    ('cloud-security-hotfix.js', security),
    ('cloud-p1-overrides.js', p1),
    ('cloud-ui-action-bridge.js', bridge),
    ('index.html', html),
):
    for forbidden in (
        'growthops_crm_token_v2',
        'localStorage.getItem(TOKEN_KEY)',
        'localStorage.setItem(TOKEN_KEY',
        'localStorage.removeItem(TOKEN_KEY',
    ):
        if forbidden in text:
            raise SystemExit(f'HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED {forbidden} survived in {name}')

if '/rest/v1/rpc/' in adapter:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED browser adapter still calls Supabase RPC directly')
if 'SUPABASE_URL' in adapter or 'API_KEY' in adapter:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED browser adapter still carries Supabase transport config')

for required in (
    "const SESSION_MARKER='cookie';",
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    "setTimeout(hide,10000)",
):
    if required not in security:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED credential safety marker missing: ' + required)
for forbidden in (
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "flattenSecretFields(bundle",
):
    if forbidden in security:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED broader reveal browser path survived: ' + forbidden)

if "const TOKEN_KEY='growthops_crm_token_v2'" in bridge or 'localStorage.getItem(TOKEN_KEY)' in bridge:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED UI bridge still depends on browser-readable CRM token')
if "document.documentElement.classList.add('growthops-session-restoring')" not in html:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED cookie restore cover missing')

for path in sorted(dist.rglob('*')):
    if not path.is_file() or path.suffix not in {'.js', '.html'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    if 'growthops_crm_token_v2' in text:
        raise SystemExit(f'HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED legacy CRM token key survived in {path.relative_to(root)}')
    if '/rest/v1/rpc/' in text:
        raise SystemExit(f'HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED direct Supabase RPC transport survived in {path.relative_to(root)}')

for forbidden in ('service_role', 'SUPABASE_SERVICE_ROLE_KEY'):
    if forbidden in api:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED privileged Supabase key marker present in API source')
if "return json(res, 200, stripSessionToken(data));" not in api:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED successful login is not token-stripped')

print('HTTP_ONLY_SESSION_OUTPUT_TESTS_OK: browser_token_storage=none; legacy_token_scrub=enabled; transport=same-origin-bff; cookie=__Host+Path-root+host-only+HttpOnly+Secure+SameSiteStrict; credential_reveal=v5-single-value')
