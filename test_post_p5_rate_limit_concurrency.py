from pathlib import Path
import re

root = Path(__file__).resolve().parent
migration = (root / 'supabase/migrations/20260825_post_p5_rate_limit_concurrency.sql').read_text(encoding='utf-8')
rollback = (root / 'supabase/rollback/20260825_post_p5_rate_limit_concurrency.sql').read_text(encoding='utf-8')
preflight = (root / 'supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql').read_text(encoding='utf-8')
postcheck = (root / 'supabase/baseline/post_p5_rate_limit_concurrency_check.sql').read_text(encoding='utf-8')
vercel = (root / 'api/crm.js').read_text(encoding='utf-8')
cloudflare = (root / 'functions/api/crm.js').read_text(encoding='utf-8')
p2b = (root / 'test_cloudflare_p2b_api.mjs').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, msg):
    if not ok:
        raise SystemExit(msg)


def strip_comments(text):
    return re.sub(r'--[^\n]*', '', text)


m = migration.lower()
r = rollback.lower()

# Fail closed if the package drifts away from the exact accepted predecessor.
for fingerprint in (
    'd3af3bfea698eab3b6592da29ef3329a',
    '0d40dda5b2bc99af44e5c39e5295b513',
    'd5825feb1a40aad7d9b65fe6e7491b7d',
):
    require(fingerprint in migration, f'migration preflight missing predecessor fingerprint: {fingerprint}')

# Exactly three existing functions may be replaced. No helper/table/sequence or
# schema object is introduced by this package.
require(m.count('create or replace function') == 3, 'migration must replace exactly three functions')
for name in ('crm_login(', 'crm_unlock_credentials_v1(', 'crm_reveal_client_secret_value_v5('):
    require(name in m, f'migration missing target: {name}')
for forbidden in ('create table', 'create sequence', 'create trigger', 'create event trigger', 'alter table'):
    require(forbidden not in m, f'migration unexpectedly changes schema shape: {forbidden}')

# Transaction-level advisory locks only. Distinct two-int namespaces prevent
# cross-domain coupling; session-level and try-lock variants are forbidden.
for namespace in ('90813011', '90813012', '90813013'):
    require(m.count(namespace) >= 2, f'migration missing lock namespace/post-check: {namespace}')
require(m.count('pg_catalog.pg_advisory_xact_lock(') == 3,
        'migration must contain exactly three transaction advisory lock calls')
for forbidden in ('pg_advisory_lock(', 'pg_try_advisory', 'pg_advisory_unlock'):
    require(forbidden not in m, f'migration contains unsafe advisory-lock form: {forbidden}')

# Lock ordering must cover count -> decision -> audit write for each subject.
def block(start, end=None):
    s = m.index(start)
    e = m.index(end, s + len(start)) if end else len(m)
    return m[s:e]

login = block('create or replace function public.crm_login(', 'create or replace function public.crm_unlock_credentials_v1(')
unlock = block('create or replace function public.crm_unlock_credentials_v1(', 'create or replace function public.crm_reveal_client_secret_value_v5(')
reveal = block('create or replace function public.crm_reveal_client_secret_value_v5(', '-- preserve exact post-p5 execute boundaries')
require(login.index('90813011') < login.index('select count(*) into v_pair_failures'), 'login lock must precede failure counts')
require(unlock.index('90813012') < unlock.index('select count(*) into v_recent_failures'), 'unlock lock must precede failure count')
require(reveal.index('90813013') < reveal.index('select count(*) into v_recent_5m'), 'reveal lock must precede reveal counts')

# Existing thresholds and source/unlock/Vault security contracts must survive.
for marker in (
    "v_pair_failures >= 12 or v_source_failures >= 50",
    "v_recent_failures >= 5",
    "v_recent_5m >= 10 or v_recent_1h >= 40",
    "v_limit_version text := 'field-v1'",
    "v_field not in ('password','twofa')",
    "v_platform not in ('facebook','tiktok','google','instagram')",
    'u.unlock_hash = v_unlock_hash',
    'u.session_token_hash = v_session_hash',
    'v_tree := public.crm_read_workspace_secrets(c.workspace_id)',
    'public.crm_secret_value_text_v5(',
    "octet_length(coalesce(p_password,'')) > 72",
    "v_headers->>'x-growthops-source-bucket'",
):
    require(marker in m, f'migration lost security marker: {marker}')

# Rejected unlocks and throttled v5 reveals must return safe envelopes rather than
# raise after writing their audit row; otherwise PostgreSQL rolls the audit write back.
require(unlock.count("return jsonb_build_object('error','credential_unlock_invalid')") == 2,
        'unlock invalid paths must both return committable error envelopes')
require("return jsonb_build_object('error','credential_unlock_throttled')" in unlock,
        'unlock throttle must return a committable envelope')
require("raise exception 'credential_unlock_invalid'" not in unlock,
        'unlock invalid path still rolls back its failure audit')
require("raise exception 'credential_unlock_throttled'" not in unlock,
        'unlock throttle still rolls back its audit')
require("return jsonb_build_object('error','credential_reveal_throttled')" in reveal,
        'v5 throttle must return a committable envelope')
require("raise exception 'credential_reveal_throttled'" not in reveal,
        'v5 throttle still rolls back its audit')

# Rollback must be the lock-free predecessor and restore exception semantics.
require(r.count('create or replace function') == 3, 'rollback must restore exactly three functions')
require('pg_advisory_xact_lock' not in r, 'rollback must remove the new transaction locks')
require("raise exception 'credential_unlock_invalid'" in r, 'rollback missing old unlock-invalid exception')
require("raise exception 'credential_unlock_throttled'" in r, 'rollback missing old unlock-throttle exception')
require("raise exception 'credential_reveal_throttled'" in r, 'rollback missing old reveal-throttle exception')
for marker in (
    'revoke all on function public.crm_login(text,text) from public, anon, authenticated, service_role;',
    'grant execute on function public.crm_unlock_credentials_v1(text,text) to service_role;',
    'grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) to service_role;',
):
    require(marker in r, f'rollback ACL drift: {marker}')

# Baseline SQL files are evidence-only.
for raw, label in ((preflight, 'preflight'), (postcheck, 'post-check')):
    body = strip_comments(raw)
    require(not re.search(r'(?im)^\s*(grant|revoke|create|alter|drop|insert|update|delete|truncate|do|begin|commit|rollback)\b', body),
            f'{label} must remain read-only')

# Both BFFs must map only the newly committable DB error envelopes back to the
# existing safe HTTP status contract. Unknown envelopes fail closed.
for source, label in ((vercel, 'Vercel'), (cloudflare, 'Cloudflare')):
    require('function committedRpcError' in source, f'{label} missing committed error bridge')
    for marker in (
        "rpc === 'crm_unlock_credentials_v1'",
        "rpc === 'crm_reveal_client_secret_value_v5'",
        "CREDENTIAL_UNLOCK_INVALID",
        "CREDENTIAL_UNLOCK_THROTTLED",
        "CREDENTIAL_REVEAL_THROTTLED",
        "UPSTREAM_REQUEST_FAILED",
    ):
        require(marker in source, f'{label} missing committed error marker: {marker}')
    require("'crm_bootstrap_admin'" not in source, f'{label} must not expose bootstrap')

for marker in (
    "okJson({error:'CREDENTIAL_UNLOCK_INVALID'})",
    "okJson({error:'CREDENTIAL_UNLOCK_THROTTLED'})",
    "okJson({error:'CREDENTIAL_REVEAL_THROTTLED'})",
    "okJson({error:'DO_NOT_EXPOSE_INTERNAL_ERROR'})",
):
    require(marker in p2b, f'cross-platform runtime test missing committed error case: {marker}')

require(build.count('python3 test_post_p5_rate_limit_concurrency.py') == 1,
        'canonical build must execute rate-limit concurrency package gate exactly once')

print(
    'POST_P5_RATE_LIMIT_CONCURRENCY_PACKAGE_OK: '
    'locks=login-source+unlock-user+reveal-user-xact; '
    'unlock-failures=committable; reveal-throttle=committable; '
    'thresholds=preserved; acl=preserved; production-change=pending'
)
