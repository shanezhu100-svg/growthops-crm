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
cloudflare = cloudflare_path.read_text(encoding='utf-8')

constant_old = "const MAX_BODY_BYTES = 4 * 1024 * 1024;\n"
constant_new = "const MAX_BODY_BYTES = 4 * 1024 * 1024;\nconst UPSTREAM_TIMEOUT_MS = 15 * 1000;\n"
vercel = replace_once(vercel, constant_old, constant_new, 'upstream timeout constant', 'vercel')
cloudflare = replace_once(cloudflare, constant_old, constant_new, 'upstream timeout constant', 'cloudflare')

vercel_old = """  const response = await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`, {
    method: 'POST',
    headers,
    redirect: 'error',
    body: JSON.stringify(args || {}),
  });
"""
vercel_new = """  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`, {
      method: 'POST',
      headers,
      redirect: 'error',
      signal: controller.signal,
      body: JSON.stringify(args || {}),
    });
  } finally {
    clearTimeout(timeoutId);
  }
"""
vercel = replace_once(vercel, vercel_old, vercel_new, 'upstream fetch timeout', 'vercel')

cloudflare_old = "const response=await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`,{method:'POST',headers,redirect:'error',body:JSON.stringify(args||{})});"
cloudflare_new = "const controller=new AbortController(); const timeoutId=setTimeout(()=>controller.abort(),UPSTREAM_TIMEOUT_MS); let response; try{response=await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`,{method:'POST',headers,redirect:'error',signal:controller.signal,body:JSON.stringify(args||{})});}finally{clearTimeout(timeoutId);}"
cloudflare = replace_once(cloudflare, cloudflare_old, cloudflare_new, 'upstream fetch timeout', 'cloudflare')

for label, source, markers in (
    ('vercel', vercel, ('UPSTREAM_TIMEOUT_MS = 15 * 1000', 'new AbortController()', 'signal: controller.signal', 'clearTimeout(timeoutId)')),
    ('cloudflare', cloudflare, ('UPSTREAM_TIMEOUT_MS = 15 * 1000', 'new AbortController()', 'signal:controller.signal', 'clearTimeout(timeoutId)')),
):
    for marker in markers:
        if marker not in source:
            raise SystemExit(f'{label}: missing upstream timeout marker: {marker}')

vercel_path.write_text(vercel, encoding='utf-8')
cloudflare_path.write_text(cloudflare, encoding='utf-8')
print('UPSTREAM_TIMEOUT_FINALIZE_OK: vercel=15s-abort; cloudflare=15s-abort; timeout-errors=existing-generic-502-path')
