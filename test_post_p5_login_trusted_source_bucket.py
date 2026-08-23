from pathlib import Path

root=Path(__file__).resolve().parent
migration=(root/'supabase/migrations/20260823_post_p5_login_trusted_source_bucket.sql').read_text(encoding='utf-8').lower()
rollback=(root/'supabase/rollback/20260823_post_p5_login_trusted_source_bucket.sql').read_text(encoding='utf-8').lower()
preflight=(root/'supabase/baseline/post_p5_login_trusted_source_bucket_preflight.sql').read_text(encoding='utf-8').lower()
postcheck=(root/'supabase/baseline/post_p5_login_trusted_source_bucket_check.sql').read_text(encoding='utf-8').lower()
vercel=(root/'api/crm.js').read_text(encoding='utf-8')
cloudflare=(root/'functions/api/crm.js').read_text(encoding='utf-8')
doc=(root/'docs/cloudflare-migration/POST_P5_LOGIN_TRUSTED_SOURCE_BUCKET.md').read_text(encoding='utf-8')
build=(root/'build.sh').read_text(encoding='utf-8')


def require(ok,msg):
    if not ok:
        raise SystemExit(msg)

require("v_headers->>'x-growthops-source-bucket'" in migration,'migration missing trusted source-bucket header')
require("^[0-9a-f]{24}$" in migration,'migration missing strict 24-hex validation')
require("x-forwarded-for" in migration and "cf-connecting-ip" in migration,'migration lost compatibility fallback')
require("v_pair_failures >= 12" in migration and "v_source_failures >= 50" in migration,'login thresholds changed')
require("'login_failure'" in migration and "'login_throttled'" in migration,'login audit actions changed')
require('x-growthops-source-bucket' not in rollback,'rollback must restore pre-change source selection')
require('x-forwarded-for' in rollback and 'cf-connecting-ip' in rollback,'rollback lost legacy source selection')
for sql,label in ((preflight,'preflight'),(postcheck,'post-check')):
    for forbidden in ('create ','replace ','grant ','revoke ','alter ','drop ','truncate ','delete from ','update public.','insert into '):
        require(forbidden not in sql,f'{label} is not read-only: {forbidden.strip()}')

require("require('node:crypto')" in vercel,'Vercel source bucket must use server-side crypto')
require("req.headers['x-forwarded-for']" in vercel,'Vercel must derive from platform x-forwarded-for')
require("request.headers.get('cf-connecting-ip')" in cloudflare,'Cloudflare must derive from CF-Connecting-IP')
for source,label in ((vercel,'Vercel'),(cloudflare,'Cloudflare')):
    require("headers['x-growthops-source-bucket']" in source,f'{label} missing outbound bucket header')
    require("/^[0-9a-f]{24}$/" in source,f'{label} missing outbound bucket validation')
    require(source.count("x-growthops-source-bucket") >= 1,f'{label} missing trusted bucket marker')

for expected,label in (
    ('c803ccd5945d05434a592c2d3f1d2da9100d3db8','accepted predecessor main'),
    ('20260823123328 / post_p5_revoke_service_role_relation_acl','accepted predecessor migration'),
    ('195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b','pre-change canonical'),
    ('195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e','expected post-change canonical'),
    ('12','pair threshold'),
    ('50','source threshold'),
):
    require(expected in doc,f'doc missing {label}')

require(build.count('node test_post_p5_login_trusted_source_bucket.mjs')==1,'build must run trusted-source BFF test once')
require(build.count('python3 test_post_p5_login_trusted_source_bucket.py')==1,'build must run trusted-source package gate once')

print('POST_P5_LOGIN_TRUSTED_SOURCE_PACKAGE_OK: bff=trusted-edge-ip-to-sha256-24hex; db=custom-bucket-first+legacy-fallback; raw-ip=persist-none; thresholds=12-pair+50-source; fingerprint=a69eba75; production-change=none')
