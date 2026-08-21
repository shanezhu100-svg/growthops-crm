from pathlib import Path

root = Path(__file__).resolve().parent
dist = root / 'dist'
api = (root / 'api' / 'crm.js').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')
security = (dist / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
p1 = (dist / 'cloud-p1-overrides.js').read_text(encoding='utf-8')

required_api = (
    "const COOKIE_NAME = '__Host-growthops_crm';",
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
    "'crm_reveal_client_secret_field_v4'",
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

required_adapter = (
    "const SESSION_MARKER='cookie';",
    "fetch('/api/crm'",
    "credentials:'same-origin'",
    "JSON.stringify({rpc:name,args:body})",
    "token=SESSION_MARKER;revision=Number(d?.revision||0);",
    "rpc('crm_login_v3'",
    "rpc('crm_load_state_v3'",
)
missing = [marker for marker in required_adapter if marker not in adapter]
if missing:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED missing adapter markers: ' + ', '.join(missing))

for name, text in (
    ('cloud-adapter.js', adapter),
    ('cloud-security-hotfix.js', security),
    ('cloud-p1-overrides.js', p1),
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
    "crm_reveal_client_secret_field_v4",
    "setTimeout(hide,10000)",
):
    if required not in security:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED credential safety marker missing: ' + required)

# No shipped browser artifact may retain the old CRM bearer-token key or direct REST
# RPC transport. The server-side BFF is intentionally excluded from this scan.
for path in sorted(dist.rglob('*')):
    if not path.is_file() or path.suffix not in {'.js', '.html'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    if 'growthops_crm_token_v2' in text:
        raise SystemExit(f'HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED legacy CRM token key survived in {path.relative_to(root)}')
    if '/rest/v1/rpc/' in text:
        raise SystemExit(f'HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED direct Supabase RPC transport survived in {path.relative_to(root)}')

# Defensive API checks: the BFF may use the public/publishable key but must never
# embed a service-role secret or echo a login token back to JavaScript.
for forbidden in ('service_role', 'SUPABASE_SERVICE_ROLE_KEY'):
    if forbidden in api:
        raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED privileged Supabase key marker present in API source')
if "return json(res, 200, stripSessionToken(data));" not in api:
    raise SystemExit('HTTP_ONLY_SESSION_OUTPUT_TESTS_FAILED successful login is not token-stripped')

print('HTTP_ONLY_SESSION_OUTPUT_TESTS_OK: browser_token_storage=none; transport=same-origin-bff; cookie=HttpOnly+Secure+SameSiteStrict')
