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
    require('HttpOnly; Secure; SameSite=Strict' in source, f'{label}: secure cookie flags missing')
    require('GROWTHOPS_SUPABASE_SECRET_KEY' in source and 'sb_secret_' in source,
            f'{label}: server secret identity requirement missing')
    require('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY' not in source and 'sb_publishable_' not in source,
            f'{label}: publishable-key fallback reintroduced')
    require(('args.p_token = sessionToken' in source) or ('args.p_token=sessionToken' in source),
            f'{label}: cookie token no longer overrides browser p_token')
    require('sameOrigin' in source and 'CROSS_ORIGIN_REQUEST_BLOCKED' in source,
            f'{label}: same-origin boundary missing')

# Final shipped credential runtime must still depend on the safe summary and must
# not regress back to the retired boolean-status RPC.
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
require('crm_read_workspace_secrets(c.workspace_id)' in low, 'safe-summary no longer workspace-scoped to Vault tree')
require('crm_reveal' not in low, 'safe-summary must never call a reveal RPC')

# Enforce the intentionally narrow output schema. Password fields may be read as
# inputs to boolean presence checks, but never placed directly into the returned
# JSON object.
return_pos = low.find('return jsonb_build_object(')
require(return_pos >= 0, 'safe-summary return object not found')
return_block = low[return_pos:]
for key in ('clientid', 'facebook', 'tiktok', 'googleaccounts', 'instagramaccounts', 'loginaccount', 'haspassword', 'has2fa'):
    require(f"'{key}'" in return_block, f'safe-summary expected output key missing: {key}')
require("'password'," not in return_block, 'safe-summary started returning a password field')
require("'2fa'," not in return_block, 'safe-summary started returning a 2FA field')
require("'loginpassword'," not in return_block, 'safe-summary started returning loginPassword directly')
require("'login_password'," not in return_block, 'safe-summary started returning login_password directly')
require("'value'," not in return_block, 'safe-summary started returning a generic secret value field')
require("'haspassword',public.crm_secret_value_nonempty" in return_block.replace(' ', ''),
        'safe-summary hasPassword is no longer derived as a boolean presence check')
require("'has2fa'," in return_block.replace(' ', ''),
        'safe-summary has2FA presence field missing')
require('password / 2fa values are never returned by this rpc' in low,
        'safe-summary migration lost explicit no-plaintext contract')

# Preparation-only guard: no Group 4 forward/rollback SQL may exist yet.
for folder in (root / 'supabase' / 'migrations', root / 'supabase' / 'rollback'):
    for path in folder.glob('*'):
        lowered = path.name.lower()
        require(not ('p5' in lowered and 'group4' in lowered),
                f'Group 4 SQL appeared during preparation stage: {path.name}')

require('No Group 4 forward `REVOKE` migration is included yet.' in doc,
        'Group 4 doc lost no-forward-migration guard')
require('No Group 4 rollback migration is included yet.' in doc,
        'Group 4 doc lost no-rollback guard')
require('must not advance ahead of Groups 1–3' in doc,
        'Group 4 doc lost predecessor-chain gate')

print(
    'P5_GROUP4_SAFE_SUMMARY_CANDIDATE_OK: '
    'safe-summary=auth-only-bff+final-runtime; output=identifier+presence-booleans-only; '
    'reveal-call=none; production-change=none'
)
