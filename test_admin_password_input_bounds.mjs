import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const SECRET='sb_secret_test_admin_password_bounds_20260824';
const ORIGIN='https://crm.example';
const COOKIE='__Host-growthops_crm='+'a'.repeat(64);
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes('upsertPasswordInputValid'));
  assert.ok(source.includes("rpc === 'crm_upsert_user'")||source.includes("rpc==='crm_upsert_user'"));
  assert.ok(source.includes('LOGIN_PASSWORD_MAX_BYTES'));
  assert.ok(source.includes("message: 'INVALID_REQUEST'")||source.includes("message:'INVALID_REQUEST'"));
}

const baseArgs={
  p_user_id:null,
  p_name:'Test Admin',
  p_username:'test-admin',
  p_role:'ADMIN',
  p_enabled:true,
};
const upstreamReply={id:'target-user',name:'Test Admin',username:'test-admin',role:'ADMIN',enabled:true};
const commonHeaders={
  'sec-fetch-site':'same-origin',
  origin:ORIGIN,
  host:'crm.example',
  'x-forwarded-host':'crm.example',
  'x-forwarded-proto':'https',
  'content-type':'application/json',
};

function makeRes(){
  const headers=Object.create(null);
  return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};
}
function parse(text){try{return JSON.parse(text);}catch{return null;}}

async function invokeVercel(password,{authenticated=true}={}){
  let calls=0;
  const oldFetch=global.fetch;
  const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=SECRET;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={...commonHeaders};
  if(authenticated)headers.cookie=COOKIE;
  const res=makeRes();
  const args={...baseArgs,p_password:password};
  try{
    await vercelHandler({method:'POST',headers,body:{rpc:'crm_upsert_user',args}},res);
    return{status:res.statusCode,json:parse(res.body),calls};
  }finally{
    global.fetch=oldFetch;
    if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;
  }
}

async function invokeCf(password,{authenticated=true}={}){
  let calls=0;
  const oldFetch=global.fetch;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={...commonHeaders};
  if(authenticated)headers.cookie=COOKIE;
  const request=new Request(`${ORIGIN}/api/crm`,{method:'POST',headers,body:JSON.stringify({rpc:'crm_upsert_user',args:{...baseArgs,p_password:password}})});
  try{
    const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:SECRET}});
    return{status:response.status,json:parse(await response.text()),calls};
  }finally{global.fetch=oldFetch;}
}

for(const invoke of [invokeVercel,invokeCf]){
  for(const password of ['p'.repeat(73),'你'.repeat(25),123,{bad:true}]){
    const result=await invoke(password);
    assert.equal(result.status,400);
    assert.deepEqual(result.json,{message:'INVALID_REQUEST'});
    assert.equal(result.calls,0);
  }

  for(const password of ['p'.repeat(72),'',null]){
    const result=await invoke(password);
    assert.equal(result.status,200);
    assert.equal(result.calls,1);
    assert.equal(result.json.id,'target-user');
  }

  const unauthenticated=await invoke('p'.repeat(73),{authenticated:false});
  assert.equal(unauthenticated.status,401);
  assert.deepEqual(unauthenticated.json,{message:'SESSION_REQUIRED'});
  assert.equal(unauthenticated.calls,0);
}

console.log('CRM_ADMIN_PASSWORD_INPUT_BOUNDS_OK: platforms=vercel+cloudflare; bcrypt-password<=72B; utf8-byte-count=active; invalid=400+zero-fetch; empty+null-update=preserved; auth-order=preserved');
