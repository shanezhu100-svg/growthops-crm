from pathlib import Path

root = Path(__file__).resolve().parent
vercel_path = root / 'api' / 'crm.js'
cloudflare_path = root / 'functions' / 'api' / 'crm.js'
vercel = vercel_path.read_text(encoding='utf-8')
cloudflare = cloudflare_path.read_text(encoding='utf-8')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)


vercel_old = """function serverConfig() {
  const key = String(process.env.GROWTHOPS_SUPABASE_SECRET_KEY || '').trim();
  const url = supabaseOrigin(process.env.GROWTHOPS_SUPABASE_URL);
  if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(key) || !url) return null;
  return { url, key };
}
"""
vercel_new = """function serverConfig() {
  const key = String(process.env.GROWTHOPS_SUPABASE_SECRET_KEY || '').trim();
  const rawUrl = String(process.env.GROWTHOPS_SUPABASE_URL || '').trim();
  const isPreview = String(process.env.VERCEL_ENV || '').trim().toLowerCase() === 'preview';
  const url = supabaseOrigin(rawUrl);
  if (isPreview && (!rawUrl || url === SUPABASE_URL_DEFAULT)) return null;
  if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(key) || !url) return null;
  return { url, key };
}
"""

cloudflare_constant_old = "const SUPABASE_URL_DEFAULT = 'https://avahcwyxparbcjdfglzx.supabase.co';\nconst COOKIE_NAME = '__Host-growthops_crm';"
cloudflare_constant_new = "const SUPABASE_URL_DEFAULT = 'https://avahcwyxparbcjdfglzx.supabase.co';\nconst CLOUDFLARE_PRODUCTION_HOST = 'growthops-crm.pages.dev';\nconst COOKIE_NAME = '__Host-growthops_crm';"
cloudflare_old = "function serverConfig(env={}){ const key=String(env.GROWTHOPS_SUPABASE_SECRET_KEY||'').trim(); const url=supabaseOrigin(env.GROWTHOPS_SUPABASE_URL); if(!/^sb_secret_[A-Za-z0-9_-]+$/.test(key)||!url) return null; return {url,key}; }"
cloudflare_new = "function serverConfig(env={},requestUrl=''){ const key=String(env.GROWTHOPS_SUPABASE_SECRET_KEY||'').trim(); const rawUrl=String(env.GROWTHOPS_SUPABASE_URL||'').trim(); let requestHost=''; try{requestHost=String(new URL(requestUrl).hostname||'').toLowerCase().replace(/\\.$/,'');}catch{} const isPagesPreview=requestHost.endsWith(`.${CLOUDFLARE_PRODUCTION_HOST}`); const url=supabaseOrigin(rawUrl); if(isPagesPreview&&(!rawUrl||url===SUPABASE_URL_DEFAULT))return null; if(!/^sb_secret_[A-Za-z0-9_-]+$/.test(key)||!url)return null; return {url,key}; }"
cloudflare_call_old = "const config=serverConfig(env); if(!config){ safeLog('server_identity_missing',requestIdValue,rpc,503);"
cloudflare_call_new = "const config=serverConfig(env,request.url); if(!config){ safeLog('server_identity_missing',requestIdValue,rpc,503);"

vercel = replace_once(vercel, vercel_old, vercel_new, 'Vercel preview runtime boundary')
cloudflare = replace_once(cloudflare, cloudflare_constant_old, cloudflare_constant_new, 'Cloudflare production host constant')
cloudflare = replace_once(cloudflare, cloudflare_old, cloudflare_new, 'Cloudflare Pages preview runtime boundary')
cloudflare = replace_once(cloudflare, cloudflare_call_old, cloudflare_call_new, 'Cloudflare serverConfig request URL call')

for label, text, markers in (
    ('Vercel', vercel, ('VERCEL_ENV', "=== 'preview'", 'url === SUPABASE_URL_DEFAULT')),
    ('Cloudflare', cloudflare, ('CLOUDFLARE_PRODUCTION_HOST', "'growthops-crm.pages.dev'", 'requestHost.endsWith(`.${CLOUDFLARE_PRODUCTION_HOST}`)', 'url===SUPABASE_URL_DEFAULT', 'serverConfig(env,request.url)')),
):
    for marker in markers:
        if marker not in text:
            raise SystemExit(f'{label} preview runtime marker missing: {marker}')

if 'CF_PAGES_BRANCH' in cloudflare:
    raise SystemExit('Cloudflare runtime preview boundary must not depend on CF_PAGES_BRANCH')

vercel_path.write_text(vercel, encoding='utf-8')
cloudflare_path.write_text(cloudflare, encoding='utf-8')
print('PREVIEW_RUNTIME_BOUNDARY_FINALIZE_OK: vercel=VERCEL_ENV-preview-fail-closed; cloudflare=standard-pages-preview-host-fail-closed; explicit-staging-required-in-preview; production-default=preserved; CF_PAGES_BRANCH=not-required')
