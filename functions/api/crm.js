const SUPABASE_URL_DEFAULT = 'https://avahcwyxparbcjdfglzx.supabase.co';
const COOKIE_NAME = '__Host-growthops_crm';
const COOKIE_MAX_AGE = 7 * 24 * 60 * 60;

// Cloudflare Pages `_headers` rules do not apply to Pages Functions. Keep these
// dynamic-response headers byte-for-byte aligned with vercel.json; the build gate
// in cloudflare_headers_finalize.py verifies every key/value on every build.
const SECURITY_HEADERS = Object.freeze({
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "X-Permitted-Cross-Domain-Policies": "none",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  "Content-Security-Policy": "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; frame-src 'none'; form-action 'self'; connect-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: blob:; media-src 'self' data: blob:; worker-src 'self' blob:; manifest-src 'self'; upgrade-insecure-requests",
});

const PUBLIC_RPCS = new Set(['crm_public_status']);
const LOGIN_RPCS = new Set(['crm_login_v3']);
const AUTH_RPCS = new Set([
  'crm_load_state_v3','crm_save_state','crm_logout','crm_list_users','crm_upsert_user','crm_delete_user',
  'crm_client_account_safe_summary','crm_unlock_credentials_v1','crm_reveal_client_secret_value_v5',
]);
const ALL_RPCS = new Set([...PUBLIC_RPCS, ...LOGIN_RPCS, ...AUTH_RPCS]);
const SAFE_UPSTREAM_MESSAGES = new Set([
  'CREDENTIAL_REAUTH_REQUIRED',
  'CREDENTIAL_REVEAL_THROTTLED',
  'CREDENTIAL_UNLOCK_REQUIRED',
  'CREDENTIAL_UNLOCK_INVALID',
  'CREDENTIAL_UNLOCK_THROTTLED',
  'INVALID_CREDENTIAL_FIELD',
  'FORBIDDEN',
]);

function parseCookies(header='') { const out={}; for (const part of String(header).split(';')) { const i=part.indexOf('='); if(i<=0) continue; const k=part.slice(0,i).trim(); const raw=part.slice(i+1).trim(); try{out[k]=decodeURIComponent(raw);}catch{out[k]=raw;} } return out; }
function sessionCookie(token){return `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;}
function clearSessionCookie(){return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;}
function sameOrigin(request){ const site=String(request.headers.get('sec-fetch-site')||'').toLowerCase(); if(site&&site!=='same-origin'&&site!=='none') return false; const origin=String(request.headers.get('origin')||''); if(!origin) return true; try{return origin===new URL(request.url).origin;}catch{return false;} }
function requestId(request){ const incoming=String(request.headers.get('x-request-id')||'').trim(); if(/^[A-Za-z0-9._:-]{8,128}$/.test(incoming)) return incoming; try{if(globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();}catch{} return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
function normalizeTrustedIp(raw){ const ip=String(raw||'').split(',')[0].trim().toLowerCase(); if(!ip||ip.length>64||!/^[0-9a-f:.]+$/.test(ip)) return ''; return ip; }
async function loginSourceBucket(request){
  // Cloudflare supplies CF-Connecting-IP at the edge. Ignore any browser-chosen
  // source-bucket header and forward only a truncated SHA-256 of the trusted IP.
  const ip=normalizeTrustedIp(request.headers.get('cf-connecting-ip'));
  if(!ip||!globalThis.crypto?.subtle) return '';
  const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(ip));
  return Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('').slice(0,24);
}
function supabaseOrigin(raw){
  const value=String(raw||SUPABASE_URL_DEFAULT).trim();
  try{
    const parsed=new URL(value); const host=String(parsed.hostname||'').toLowerCase().replace(/\.$/,'');
    if(parsed.protocol!=='https:'||!host.endsWith('.supabase.co')) return '';
    if(parsed.username||parsed.password||(parsed.port&&parsed.port!=='443')) return '';
    if(parsed.pathname!=='/'||parsed.search||parsed.hash) return '';
    return `https://${host}`;
  }catch{return '';}
}
function serverConfig(env={}){ const key=String(env.GROWTHOPS_SUPABASE_SECRET_KEY||'').trim(); const url=supabaseOrigin(env.GROWTHOPS_SUPABASE_URL); if(!/^sb_secret_[A-Za-z0-9_-]+$/.test(key)||!url) return null; return {url,key}; }
function json(status,body,requestIdValue,extraHeaders={}){ const headers=new Headers({...extraHeaders,...SECURITY_HEADERS,'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store, max-age=0','Pragma':'no-cache','X-Request-ID':requestIdValue}); return new Response(JSON.stringify(body),{status,headers}); }
async function bodyObject(request){ const text=await request.text(); if(!text) return {}; try{return JSON.parse(text);}catch{return null;} }
function safeLog(event,requestIdValue,rpc,status){ console.error(JSON.stringify({event,platform:'cloudflare',requestId:requestIdValue,rpc:ALL_RPCS.has(rpc)?rpc:'unknown',status:Number(status||0)})); }
function safeUpstreamMessage(data){ const message=String(data?.message||'').trim(); return SAFE_UPSTREAM_MESSAGES.has(message)?message:''; }
async function supabaseRpc(name,args,config,sourceBucket=''){
  const headers={apikey:config.key,'Content-Type':'application/json','Cache-Control':'no-store'};
  if(/^[0-9a-f]{24}$/.test(String(sourceBucket))) headers['x-growthops-source-bucket']=String(sourceBucket);
  const response=await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`,{method:'POST',headers,body:JSON.stringify(args||{})});
  let data=null; try{data=await response.json();}catch{} if(!response.ok){ const error=new Error('UPSTREAM_RPC_FAILED'); error.status=response.status; error.safeMessage=safeUpstreamMessage(data); error.sessionRelated=/SESSION|TOKEN|UNAUTHORIZED/i.test(String(data?.message||data?.hint||'')); throw error;} return data;
}
function sanitizeUpstreamError(error){ const safeMessage=String(error?.safeMessage||''); if(safeMessage){ if(safeMessage.endsWith('_THROTTLED'))return{status:429,message:safeMessage}; if(safeMessage==='FORBIDDEN')return{status:403,message:safeMessage}; return{status:400,message:safeMessage}; } const s=Number(error?.status||0); if(s===400)return{status:400,message:'UPSTREAM_BAD_REQUEST'}; if(s===401)return{status:401,message:'SESSION_INVALID'}; if(s===403)return{status:403,message:'REQUEST_DENIED'}; if(s===404)return{status:404,message:'UPSTREAM_NOT_FOUND'}; if(s===409)return{status:409,message:'CONFLICT'}; if(s===429)return{status:429,message:'RATE_LIMITED'}; return{status:502,message:'UPSTREAM_REQUEST_FAILED'}; }
function stripSessionToken(data){ if(!data||typeof data!=='object'||Array.isArray(data)||!Object.prototype.hasOwnProperty.call(data,'token')) return data; const safe={...data}; delete safe.token; return safe; }

export async function onRequest(context){
  const request=context.request; const env=context.env||{}; const requestIdValue=requestId(request); const respond=(status,body,extra={})=>json(status,body,requestIdValue,extra);
  if(request.method!=='POST') return respond(405,{message:'METHOD_NOT_ALLOWED'},{Allow:'POST'});
  if(!sameOrigin(request)) return respond(403,{message:'CROSS_ORIGIN_REQUEST_BLOCKED'});
  const body=await bodyObject(request); if(!body) return respond(400,{message:'INVALID_JSON'});
  const rpc=String(body.rpc||''); const args=body.args&&typeof body.args==='object'&&!Array.isArray(body.args)?{...body.args}:{};
  if(!ALL_RPCS.has(rpc)) return respond(403,{message:'RPC_NOT_ALLOWED'});
  const config=serverConfig(env); if(!config){ safeLog('server_identity_missing',requestIdValue,rpc,503); return respond(503,{message:'SERVER_IDENTITY_NOT_CONFIGURED'}); }
  const cookies=parseCookies(request.headers.get('cookie')||''); const sessionToken=String(cookies[COOKIE_NAME]||'');
  try{
    if(LOGIN_RPCS.has(rpc)){ delete args.p_token; const data=await supabaseRpc(rpc,args,config,await loginSourceBucket(request)); if(data?.error) return respond(401,{message:'LOGIN_FAILED'}); const token=String(data?.token||''); if(!token) return respond(502,{message:'LOGIN_SESSION_MISSING'}); return respond(200,stripSessionToken(data),{'Set-Cookie':sessionCookie(token)}); }
    if(PUBLIC_RPCS.has(rpc)){ delete args.p_token; return respond(200,stripSessionToken(await supabaseRpc(rpc,args,config))); }
    if(!sessionToken) return respond(401,{message:'SESSION_REQUIRED'},{'Set-Cookie':clearSessionCookie()});
    args.p_token=sessionToken;
    if(rpc==='crm_logout'){ try{ const data=await supabaseRpc(rpc,args,config); return respond(200,stripSessionToken(data),{'Set-Cookie':clearSessionCookie()}); }catch(error){ error.clearSessionCookie=true; throw error; } }
    return respond(200,stripSessionToken(await supabaseRpc(rpc,args,config)));
  }catch(error){
    const upstreamStatus=Number(error?.status||0); const headers={}; if(error?.clearSessionCookie||upstreamStatus===401||error?.sessionRelated) headers['Set-Cookie']=clearSessionCookie(); const safe=sanitizeUpstreamError(error); safeLog('upstream_rpc_error',requestIdValue,rpc,upstreamStatus||safe.status); return respond(safe.status,{message:safe.message},headers);
  }
}