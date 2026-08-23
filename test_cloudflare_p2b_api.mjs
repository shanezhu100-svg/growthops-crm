import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET = 'sb_secret_test_p2b_server_identity_20260822';
const TEST_REQUEST_ID = 'p2b-request-0001';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY = TEST_SECRET;

const require = createRequire(import.meta.url);
const vercelHandler = require('./api/crm.js');
const cfSource = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');
const cfModule = await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler = cfModule.onRequest;
const vercelSource = readFileSync(new URL('./api/crm.js', import.meta.url), 'utf8');

function makeRes(){ const headers=Object.create(null); return {statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}}; }
function parseJson(text){try{return text?JSON.parse(text):null;}catch{return null;}}

async function invokeVercel({method='POST',headers={},body={},secret=TEST_SECRET}, fetchImpl){
  const oldFetch=global.fetch; const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  if(secret===null) delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY; else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=secret;
  if(fetchImpl) global.fetch=fetchImpl;
  const res=makeRes();
  try{await vercelHandler({method,headers,body},res);}finally{global.fetch=oldFetch; if(oldSecret===undefined) delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY; else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;}
  return {status:res.statusCode,headers:res.headers,json:parseJson(res.body)};
}
async function invokeCf({method='POST',headers={},body={},rawBody=null,secret=TEST_SECRET}, fetchImpl){
  const oldFetch=global.fetch; if(fetchImpl) global.fetch=fetchImpl;
  const init={method,headers}; if(method!=='GET'&&method!=='HEAD') init.body=rawBody!==null?rawBody:JSON.stringify(body);
  const request=new Request('https://preview.example/api/crm',init); let response;
  try{response=await cloudflareHandler({request,env:secret===null?{}:{GROWTHOPS_SUPABASE_SECRET_KEY:secret}});}finally{global.fetch=oldFetch;}
  const text=await response.text(); return {status:response.status,headers:{allow:response.headers.get('allow'),'cache-control':response.headers.get('cache-control'),'set-cookie':response.headers.get('set-cookie'),'x-request-id':response.headers.get('x-request-id')},json:parseJson(text)};
}
function okJson(data){return Promise.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}));}
function errJson(status,data){return Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}));}
const sameOrigin={'sec-fetch-site':'same-origin',origin:'https://preview.example',host:'preview.example','x-forwarded-host':'preview.example','x-forwarded-proto':'https','x-request-id':TEST_REQUEST_ID};

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes('GROWTHOPS_SUPABASE_SECRET_KEY'));
  assert.ok(source.includes('sb_secret_'));
  assert.equal(source.includes('GROWTHOPS_SUPABASE_PUBLISHABLE_KEY'),false);
  assert.equal(source.includes('sb_publishable_'),false);
  assert.equal(source.includes('SUPABASE_SERVICE_ROLE_KEY'),false);
  assert.equal(source.includes("'crm_reveal_client_secret_field_v4'"),false);
  assert.equal(source.includes("'crm_reveal_client_secret_field_v3'"),false);
  assert.equal(source.includes("'crm_reveal_client_secrets'"),false);
}

// Request ID and basic method/origin/allowlist parity.
for(const input of [
  {method:'GET',headers:{'x-request-id':TEST_REQUEST_ID}},
  {headers:{...sameOrigin,'sec-fetch-site':'cross-site'},body:{rpc:'crm_public_status',args:{}}},
  {headers:sameOrigin,body:{rpc:'crm_not_allowed',args:{}}},
]){
  const v=await invokeVercel(input); const c=await invokeCf(input);
  assert.equal(c.status,v.status); assert.deepEqual(c.json,v.json);
  assert.equal(v.headers['x-request-id'],TEST_REQUEST_ID); assert.equal(c.headers['x-request-id'],TEST_REQUEST_ID);
}

// Missing or wrong key fails closed before any Supabase call.
for(const secret of [null,'sb_publishable_not_allowed']){
  let calls=0; const fake=async()=>{calls++; return okJson({});};
  const input={headers:sameOrigin,body:{rpc:'crm_public_status',args:{}},secret};
  const v=await invokeVercel(input,fake); const c=await invokeCf(input,fake);
  assert.equal(v.status,503); assert.equal(c.status,503);
  assert.equal(v.json.message,'SERVER_IDENTITY_NOT_CONFIGURED'); assert.equal(c.json.message,'SERVER_IDENTITY_NOT_CONFIGURED');
  assert.equal(calls,0);
}

// Valid secret must be the only apikey sent upstream.
for(const invoke of [invokeVercel,invokeCf]){
  let capture=null;
  const result=await invoke({headers:sameOrigin,body:{rpc:'crm_public_status',args:{}}},async(url,options)=>{capture={url:String(url),headers:options.headers}; return okJson({service:'GrowthOps CRM Cloud',initialized:true});});
  assert.equal(result.status,200); assert.equal(capture.headers.apikey,TEST_SECRET); assert.equal(capture.headers.Authorization,undefined); assert.equal(result.headers['x-request-id'],TEST_REQUEST_ID);
}

// Login token stays server-side and cookie semantics stay unchanged.
for(const invoke of [invokeVercel,invokeCf]){
  let body=null;
  const result=await invoke({headers:sameOrigin,body:{rpc:'crm_login_v3',args:{p_username:'admin',p_password:'test-password',p_token:'forged'}}},async(_url,options)=>{body=JSON.parse(options.body); return okJson({token:'server-session-token',revision:7,user:{id:'u1',role:'ADMIN'},state:{}});});
  assert.equal(result.status,200); assert.equal(body.p_token,undefined); assert.equal(result.json.token,undefined);
  const cookie=String(result.headers['set-cookie']||''); assert.match(cookie,/^__Host-growthops_crm=server-session-token;/); assert.match(cookie,/HttpOnly/); assert.match(cookie,/Secure/); assert.match(cookie,/SameSite=Strict/);
}

// Cookie token overrides forged browser token; v5 remains scalar-only.
for(const rpcCase of [
  {rpc:'crm_load_state_v3',args:{p_token:'forged',p_extra:'kept'},reply:{revision:8,state:{}}},
  {rpc:'crm_reveal_client_secret_value_v5',args:{p_token:'forged',p_unlock_token:'unlock',p_client_id:'c1',p_platform:'facebook',p_account_id:'a1',p_field:'password'},reply:{value:'single-value'}},
]){
  for(const invoke of [invokeVercel,invokeCf]){
    let body=null; const result=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:rpcCase.rpc,args:rpcCase.args}},async(_url,options)=>{body=JSON.parse(options.body); return okJson(rpcCase.reply);});
    assert.equal(result.status,200); assert.equal(body.p_token,'cookie-session-token'); if(rpcCase.rpc.includes('reveal')) assert.deepEqual(result.json,{value:'single-value'});
  }
}

// Every ADMIN user-management RPC is session-gated on both BFFs. Without the
// HttpOnly cookie the upstream must not be contacted; with the cookie, any
// forged browser p_token must be replaced by the server-read cookie token.
for(const rpcCase of [
  {rpc:'crm_list_users',args:{p_token:'forged'},reply:[]},
  {rpc:'crm_upsert_user',args:{p_token:'forged',p_user_id:null,p_name:'Example',p_username:'example-user',p_password:'not-sent-upstream-in-real-test',p_role:'SALES',p_enabled:true},reply:{id:'u2',role:'SALES'}},
  {rpc:'crm_delete_user',args:{p_token:'forged',p_user_id:'00000000-0000-0000-0000-000000000002'},reply:true},
]){
  for(const invoke of [invokeVercel,invokeCf]){
    let calls=0;
    const missing=await invoke({headers:sameOrigin,body:{rpc:rpcCase.rpc,args:rpcCase.args}},async()=>{calls++; return okJson(rpcCase.reply);});
    assert.equal(missing.status,401); assert.equal(missing.json.message,'SESSION_REQUIRED'); assert.equal(calls,0);

    let requestUrl=''; let requestBody=null;
    const present=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:rpcCase.rpc,args:rpcCase.args}},async(url,options)=>{calls++; requestUrl=String(url); requestBody=JSON.parse(options.body); return okJson(rpcCase.reply);});
    assert.equal(present.status,200); assert.equal(calls,1);
    assert.ok(requestUrl.endsWith(`/rest/v1/rpc/${rpcCase.rpc}`));
    assert.equal(requestBody.p_token,'cookie-session-token');
  }
}

// Logout always clears cookie.
for(const invoke of [invokeVercel,invokeCf]){
  const result=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:'crm_logout',args:{}}},()=>okJson({ok:true}));
  assert.equal(result.status,200); assert.match(String(result.headers['set-cookie']||''),/Max-Age=0/);
}

// Upstream details and request secrets must never reach response or logs.
for(const invoke of [invokeVercel,invokeCf]){
  const logs=[]; const oldError=console.error; console.error=(...args)=>logs.push(args.join(' '));
  try{
    const result=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:'crm_save_state',args:{p_token:'forged',p_state:{password:'DO_NOT_LOG_PASSWORD',twofa:'DO_NOT_LOG_2FA'}}}},()=>errJson(500,{message:'database exploded with DO_NOT_LOG_PASSWORD and secret key material'}));
    assert.equal(result.status,502); assert.deepEqual(result.json,{message:'UPSTREAM_REQUEST_FAILED'});
    const joined=logs.join('\n'); assert.equal(joined.includes('DO_NOT_LOG_PASSWORD'),false); assert.equal(joined.includes('DO_NOT_LOG_2FA'),false); assert.equal(joined.includes(TEST_SECRET),false); assert.ok(joined.includes(TEST_REQUEST_ID)); assert.ok(joined.includes('crm_save_state'));
  }finally{console.error=oldError;}
}

// 401 is sanitized and clears the session cookie without exposing upstream text.
for(const invoke of [invokeVercel,invokeCf]){
  const result=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:'crm_load_state_v3',args:{}}},()=>errJson(401,{message:'TOKEN expired internal detail'}));
  assert.equal(result.status,401); assert.deepEqual(result.json,{message:'SESSION_INVALID'}); assert.match(String(result.headers['set-cookie']||''),/Max-Age=0/);
}

console.log('CLOUDFLARE_P2B_SERVER_IDENTITY_TESTS_OK: secret-key=required; publishable-fallback=none; request-id=active; logs=filtered; errors=sanitized; admin-user-rpcs=session-gated; v5-only; logout-clears-cookie');
