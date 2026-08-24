from pathlib import Path

root = Path(__file__).resolve().parent
vercel_path = root / 'api' / 'crm.js'
cloudflare_path = root / 'functions' / 'api' / 'crm.js'


def replace_once(text, old, new, label, platform):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{platform}: unexpected {label} count: {count}')
    return text.replace(old, new, 1)

vercel = vercel_path.read_text(encoding='utf-8')
vercel_old = """function serverConfig() {
  const key = String(process.env.GROWTHOPS_SUPABASE_SECRET_KEY || '').trim();
  const rawUrl = String(process.env.GROWTHOPS_SUPABASE_URL || '').trim();
  const isPreview = String(process.env.VERCEL_ENV || '').trim().toLowerCase() === 'preview';
  const url = supabaseOrigin(rawUrl);
  if (isPreview && (!rawUrl || url === SUPABASE_URL_DEFAULT)) return null;
  if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(key) || !url) return null;
  return { url, key };
}
"""
vercel_new = """function serverConfig() {
  const key = String(process.env.GROWTHOPS_SUPABASE_SECRET_KEY || '').trim();
  const rawUrl = String(process.env.GROWTHOPS_SUPABASE_URL || '').trim();
  const environment = String(process.env.VERCEL_ENV || '').trim().toLowerCase();
  const isPreview = environment === 'preview';
  const isProduction = environment === 'production';
  const url = supabaseOrigin(rawUrl);
  if (isPreview && (!rawUrl || url === SUPABASE_URL_DEFAULT)) return null;
  if (isProduction && url !== SUPABASE_URL_DEFAULT) return null;
  if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(key) || !url) return null;
  return { url, key };
}
"""
vercel = replace_once(vercel, vercel_old, vercel_new, 'production Supabase pin', 'vercel')

cloudflare = cloudflare_path.read_text(encoding='utf-8')
cloudflare_old = "function serverConfig(env={},requestUrl=''){ const key=String(env.GROWTHOPS_SUPABASE_SECRET_KEY||'').trim(); const rawUrl=String(env.GROWTHOPS_SUPABASE_URL||'').trim(); let requestHost=''; try{requestHost=String(new URL(requestUrl).hostname||'').toLowerCase().replace(/\\.$/,'');}catch{} const isPagesPreview=requestHost.endsWith(`.${CLOUDFLARE_PRODUCTION_HOST}`); const url=supabaseOrigin(rawUrl); if(isPagesPreview&&(!rawUrl||url===SUPABASE_URL_DEFAULT))return null; if(!/^sb_secret_[A-Za-z0-9_-]+$/.test(key)||!url)return null; return {url,key}; }"
cloudflare_new = "function serverConfig(env={},requestUrl=''){ const key=String(env.GROWTHOPS_SUPABASE_SECRET_KEY||'').trim(); const rawUrl=String(env.GROWTHOPS_SUPABASE_URL||'').trim(); let requestHost=''; try{requestHost=String(new URL(requestUrl).hostname||'').toLowerCase().replace(/\\.$/,'');}catch{} const isPagesProduction=requestHost===CLOUDFLARE_PRODUCTION_HOST; const isPagesPreview=requestHost.endsWith(`.${CLOUDFLARE_PRODUCTION_HOST}`); const url=supabaseOrigin(rawUrl); if(isPagesPreview&&(!rawUrl||url===SUPABASE_URL_DEFAULT))return null; if(isPagesProduction&&url!==SUPABASE_URL_DEFAULT)return null; if(!/^sb_secret_[A-Za-z0-9_-]+$/.test(key)||!url)return null; return {url,key}; }"
cloudflare = replace_once(cloudflare, cloudflare_old, cloudflare_new, 'production Supabase pin', 'cloudflare')

for label, source, markers in (
    ('vercel', vercel, ("isProduction = environment === 'production'", 'isProduction && url !== SUPABASE_URL_DEFAULT')),
    ('cloudflare', cloudflare, ('isPagesProduction=requestHost===CLOUDFLARE_PRODUCTION_HOST', 'isPagesProduction&&url!==SUPABASE_URL_DEFAULT')),
):
    for marker in markers:
        if marker not in source:
            raise SystemExit(f'{label}: missing production origin pin marker: {marker}')

vercel_path.write_text(vercel, encoding='utf-8')
cloudflare_path.write_text(cloudflare, encoding='utf-8')
print('PRODUCTION_SUPABASE_ORIGIN_PIN_FINALIZE_OK: vercel-production=canonical-only; cloudflare-pages-production=canonical-only; preview-staging=preserved; unknown-local-host=unchanged')
