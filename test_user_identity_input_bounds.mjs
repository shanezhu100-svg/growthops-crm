import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const SECRET='sb_secret_test_identity_bounds_20260824';
const ORIGIN='https://crm.example';
const COOKIE='__Host-growthops_crm='+'a'.repeat(64);
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes('USER_IDENTITY_MAX_BYTES'));
  assert.ok(source.includes('upsertIdentityInputValid'));
  assert.ok(source.includes("rpc === 'crm_upsert_user'")||source.includes("rpc==='crm_upsert_user'"));
  assert.ok(source.includes("message: 'INVALID_REQUEST'")||source.includes("message:'INVALID_REQUEST'"));
}

const commonHeaders={
  'sec-fetch-site':'same-origin',
  origin:ORIGIN,
  host:'crm.example',
  'x-forwarded-host':'crm.example',
  'x-forwarded-proto':'https',
  'content-type':'application/json',
};
const baseArgs={
  p_user_id:null,
  p_name:'Test Admin',
  p_username:'test-admin',
  p_password:'p'.repeat(10),
  p_role:'ADMIN',
  p_enabled:true,
};
const upstreamReply={id:'target-user',name:'Test Admin',username:'test-admin',role:'ADMIN',enabled:true};

function makeRes(){
  const headers=Object.create(null);
  return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};
}
function parse(text){try{return JSON.parse(text);}catch{return null;}}

async function invokeVercel(overrides,{authenticated=true}={}){
  let calls=0;
  const oldFetch=global.fetch;
  const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=SECRET;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={...commonHeaders};
  if(authenticated)headers.cookie=COOKIE;
  const res=makeRes();
  try{
    await vercelHandler({method:'POST',headers,body:{rpc:'crm_upsert_user',args:{...baseArgs,...overrides}}},res);
    return{status:res.statusCode,json:parse(res.body),calls};
  }finally{
    global.fetch=oldFetch;
    if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;
  }
}

async function invokeCf(overrides,{authenticated=true}={}){
  let calls=0;
  const oldFetch=global.fetch;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={...commonHeaders};
  if(authenticated)headers.cookie=COOKIE;
  const request=new Request(`${ORIGIN}/api/crm`,{method:'POST',headers,body:JSON.stringify({rpc:'crm_upsert_user',args:{...baseArgs,...overrides}})});
  try{
    const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:SECRET}});
    return{status:response.status,json:parse(await response.text()),calls};
  }finally{global.fetch=oldFetch;}
}

const invalidCases=[
  {p_name:'n'.repeat(257)},
  {p_name:'你'.repeat(86)},
  {p_username:'u'.repeat(257)},
  {p_username:'你'.repeat(86)},
  {p_name:123},
  {p_name:null},
  {p_username:{bad:true}},
  {p_username:null},
];
const validCases=[
  {p_name:'n'.repeat(256),p_username:'u'.repeat(256)},
  {p_name:'你'.repeat(85),p_username:'你'.repeat(85)},
  {p_name:'',p_username:''},
];

for(const invoke of [invokeVercel,invokeCf]){
  for(const overrides of invalidCases){
    const result=await invoke(overrides);
    assert.equal(result.status,400);
    assert.deepEqual(result.json,{message:'INVALID_REQUEST'});
    assert.equal(result.calls,0);
  }
  for(const overrides of validCases){
    const result=await invoke(overrides);
    assert.equal(result.status,200);
    assert.equal(result.calls,1);
    assert.equal(result.json.id,'target-user');
  }
  const unauthenticated=await invoke({p_username:'u'.repeat(257)},{authenticated:false});
  assert.equal(unauthenticated.status,401);
  assert.deepEqual(unauthenticated.json,{message:'SESSION_REQUIRED'});
  assert.equal(unauthenticated.calls,0);
}

console.log('CRM_USER_IDENTITY_INPUT_BOUNDS_OK: platforms=vercel+cloudflare; name+username<=256B; utf8-byte-count=active; nonstring+oversize=400+zero-fetch; empty=min-rules-deferred-to-DB; auth-order=preserved');
