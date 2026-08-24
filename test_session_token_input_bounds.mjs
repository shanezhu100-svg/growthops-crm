import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_session_token_bounds_20260824';
const VALID_64='a'.repeat(64);
const OVERSIZE_65='b'.repeat(65);
const OVERSIZE_UTF8_ENCODED=Array.from({length:17},()=>'%F0%9F%98%80').join('');
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return text?JSON.parse(text):null;}catch{return null;}}
function okJson(data){return Promise.resolve({ok:true,status:200,async json(){return data;}});}
const sameOrigin={'sec-fetch-site':'same-origin',origin:'https://session-boundary.example',host:'session-boundary.example','x-forwarded-host':'session-boundary.example','x-forwarded-proto':'https'};

async function invokeVercel({cookie='',body},fetchImpl){
  const oldFetch=global.fetch;
  const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  const oldEnv=process.env.VERCEL_ENV;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
  process.env.VERCEL_ENV='production';
  global.fetch=fetchImpl;
  const res=makeRes();
  const headers={...sameOrigin}; if(cookie)headers.cookie=`__Host-growthops_crm=${cookie}`;
  try{await vercelHandler({method:'POST',headers,body},res);}finally{
    global.fetch=oldFetch;
    if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;
    if(oldEnv===undefined)delete process.env.VERCEL_ENV;else process.env.VERCEL_ENV=oldEnv;
  }
  return{status:res.statusCode,headers:res.headers,json:parse(res.body)};
}

async function invokeCloudflare({cookie='',body},fetchImpl){
  const oldFetch=global.fetch;global.fetch=fetchImpl;
  const headers={'sec-fetch-site':'same-origin',origin:'https://session-boundary.example'};
  if(cookie)headers.cookie=`__Host-growthops_crm=${cookie}`;
  const request=new Request('https://session-boundary.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{
    const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET}});
    return{status:response.status,headers:{'set-cookie':response.headers.get('set-cookie')},json:parse(await response.text())};
  }finally{global.fetch=oldFetch;}
}

for(const [label,source] of [['Vercel',vercelSource],['Cloudflare',cfSource]]){
  assert.ok(source.includes('SESSION_TOKEN_MAX_BYTES = 64'),`${label}: missing token max`);
  assert.ok(source.includes('function sessionTokenInputValid'),`${label}: missing token helper`);
  assert.ok(source.includes('sessionTokenInputValid(sessionToken)'),`${label}: missing cookie guard`);
  assert.ok(source.includes('sessionTokenInputValid(token)'),`${label}: missing login response guard`);
}

const authBody={rpc:'crm_load_state_v3',args:{p_token:'browser-forged'}};
for(const invoke of [invokeVercel,invokeCloudflare]){
  for(const badCookie of [OVERSIZE_65,OVERSIZE_UTF8_ENCODED]){
    let calls=0;
    const result=await invoke({cookie:badCookie,body:authBody},async()=>{calls++;throw new Error('oversize cookie must not reach Supabase');});
    assert.equal(result.status,401);
    assert.equal(result.json?.message,'SESSION_REQUIRED');
    assert.match(String(result.headers['set-cookie']||''),/Max-Age=0/);
    assert.equal(calls,0);
  }

  let forwarded=null;
  const accepted=await invoke({cookie:VALID_64,body:authBody},async(_url,options)=>{forwarded=JSON.parse(options.body);return okJson({revision:1,state:{}});});
  assert.equal(accepted.status,200);
  assert.equal(forwarded?.p_token,VALID_64);
  assert.notEqual(forwarded?.p_token,'browser-forged');

  const loginBody={rpc:'crm_login_v3',args:{p_username:'admin',p_password:'test-password'}};
  const oversizedLogin=await invoke({body:loginBody},async()=>okJson({token:OVERSIZE_65,revision:1,user:{id:'u1',role:'ADMIN'},state:{}}));
  assert.equal(oversizedLogin.status,502);
  assert.equal(oversizedLogin.json?.message,'LOGIN_SESSION_MISSING');
  assert.equal(oversizedLogin.headers['set-cookie']||null,null);

  const validLogin=await invoke({body:loginBody},async()=>okJson({token:VALID_64,revision:1,user:{id:'u1',role:'ADMIN'},state:{}}));
  assert.equal(validLogin.status,200);
  assert.match(String(validLogin.headers['set-cookie']||''),new RegExp(`^__Host-growthops_crm=${VALID_64};`));
  assert.equal(validLogin.json?.token,undefined);
}

console.log('SESSION_TOKEN_INPUT_BOUNDS_OK: platforms=vercel+cloudflare; valid-boundary=64B; ascii+utf8-oversize-cookie=401+clear+zero-fetch; forged-body-token=replaced; oversize-login-token=502+no-cookie');
