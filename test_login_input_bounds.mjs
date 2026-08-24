import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const SECRET='sb_secret_test_login_input_bounds_20260824';
const ORIGIN='https://crm.example';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes('LOGIN_USERNAME_MAX_BYTES = 256'));
  assert.ok(source.includes('LOGIN_PASSWORD_MAX_BYTES = 72'));
  assert.ok(source.includes('loginInputValid'));
  assert.ok(source.includes("{ message: 'LOGIN_FAILED' }")||source.includes("{message:'LOGIN_FAILED'}"));
}

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return JSON.parse(text);}catch{return null;}}
const baseHeaders={'sec-fetch-site':'same-origin',origin:ORIGIN,host:'crm.example','x-forwarded-host':'crm.example','x-forwarded-proto':'https','content-type':'application/json'};
const upstreamReply={token:'server-session-token',revision:1,user:{id:'u1',role:'ADMIN'},state:{}};

async function invokeVercel(args){
  let calls=0;const oldFetch=global.fetch;const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=SECRET;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const res=makeRes();
  try{await vercelHandler({method:'POST',headers:baseHeaders,body:{rpc:'crm_login_v3',args}},res);}finally{global.fetch=oldFetch;if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;}
  return{status:res.statusCode,json:parse(res.body),calls};
}
async function invokeCf(args){
  let calls=0;const oldFetch=global.fetch;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify(upstreamReply),{status:200,headers:{'Content-Type':'application/json'}});};
  const request=new Request(`${ORIGIN}/api/crm`,{method:'POST',headers:baseHeaders,body:JSON.stringify({rpc:'crm_login_v3',args})});
  try{const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:SECRET}});return{status:response.status,json:parse(await response.text()),calls};}finally{global.fetch=oldFetch;}
}

for(const invoke of [invokeVercel,invokeCf]){
  const valid=await invoke({p_username:'u'.repeat(256),p_password:'p'.repeat(72),p_token:'forged'});
  assert.equal(valid.status,200);assert.equal(valid.calls,1);assert.equal(valid.json.token,undefined);

  for(const args of [
    {p_username:'u'.repeat(257),p_password:'ok'},
    {p_username:'ok',p_password:'p'.repeat(73)},
    {p_username:'ok',p_password:'你'.repeat(25)},
    {p_username:'你'.repeat(86),p_password:'ok'},
    {p_username:123,p_password:'ok'},
    {p_username:'ok',p_password:null},
    {p_username:'ok'},
    {p_password:'ok'},
  ]){
    const result=await invoke(args);
    assert.equal(result.status,401);assert.deepEqual(result.json,{message:'LOGIN_FAILED'});assert.equal(result.calls,0);
  }
}

console.log('CRM_LOGIN_INPUT_BOUNDS_OK: platforms=vercel+cloudflare; username<=256B; bcrypt-password<=72B; utf8-byte-count=active; invalid-input=401-generic+zero-fetch; valid-boundary=preserved');
