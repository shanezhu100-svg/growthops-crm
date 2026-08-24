from pathlib import Path

root = Path(__file__).resolve().parent
migration = (root / 'supabase/migrations/20260824_post_p5_v5_direct_scalar.sql').read_text(encoding='utf-8')
preflight = (root / 'supabase/baseline/post_p5_v5_direct_scalar_preflight.sql').read_text(encoding='utf-8')
check = (root / 'supabase/baseline/post_p5_v5_direct_scalar_check.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase/rollback/20260824_post_p5_v5_direct_scalar_rollback.sql').read_text(encoding='utf-8')
api = (root / 'api/crm.js').read_text(encoding='utf-8')
cf_api = (root / 'functions/api/crm.js').read_text(encoding='utf-8')

required_migration = (
    'create or replace function public.crm_reveal_client_secret_value_v5',
    "v_field not in ('password','twofa')",
    "v_platform not in ('facebook','tiktok','google','instagram')",
    'u.unlock_hash = v_unlock_hash',
    'u.session_token_hash = v_session_hash',
    'u.expires_at > now()',
    "l.action = 'REVEAL_CLIENT_SECRET_FIELD'",
    "l.action = 'REVEAL_CLIENT_SECRET_FIELD_THROTTLED'",
    'v_recent_5m >= 10 or v_recent_1h >= 40',
    "v_limit_version text := 'field-v1'",
    'v_tree := public.crm_read_workspace_secrets(c.workspace_id)',
    'public.crm_strip_login_identifier_secrets(v_account)',
    'public.crm_secret_value_text_v5(',
    "return jsonb_build_object('value', v_value)",
    'from public, anon, authenticated;',
    'to service_role;',
)
missing = [m for m in required_migration if m not in migration]
if missing:
    raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED migration missing: ' + ', '.join(missing))

for forbidden in (
    'crm_reveal_client_secret_field_v3(',
    'crm_reveal_client_secret_field_v4(',
    'crm_reveal_client_secrets(',
    "jsonb_build_object('accountSecrets'",
):
    if forbidden in migration:
        raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED broad dependency in migration: ' + forbidden)

if 'expected current v3 composition not found' not in preflight or 'crm_reveal_client_secret_field_v3' not in preflight:
    raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED preflight does not pin current composition')
if 'broader reveal dependency remains' not in check or 'v5 ACL drift' not in check:
    raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED post-check incomplete')
if 'crm_reveal_client_secret_field_v3(' not in rollback:
    raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED rollback does not restore v3 composition')
if 'from public, anon, authenticated;' not in rollback or 'to service_role;' not in rollback:
    raise SystemExit('POST_P5_V5_DIRECT_SCALAR_TEST_FAILED rollback would weaken Post-P5 ACL')

for name, source in (('vercel', api), ('cloudflare', cf_api)):
    if "'crm_reveal_client_secret_value_v5'" not in source:
        raise SystemExit(f'POST_P5_V5_DIRECT_SCALAR_TEST_FAILED {name} BFF missing v5')
    for forbidden in (
        "'crm_reveal_client_secret_field_v3'",
        "'crm_reveal_client_secret_field_v4'",
        "'crm_reveal_client_secrets'",
    ):
        if forbidden in source:
            raise SystemExit(f'POST_P5_V5_DIRECT_SCALAR_TEST_FAILED {name} BFF exposes {forbidden}')

print('POST_P5_V5_DIRECT_SCALAR_TESTS_OK: v5=direct-vault-scalar; exact-unlock=preserved; rate-limit=field-v1-preserved; audit=preserved; rollback=v3-internal; browser-broad-rpc=closed')
