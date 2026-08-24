import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const MAX = 4 * 1024 * 1024;
const SECRET='sb_secret_test_body_limit_20260824';
const ORIGIN='https://crm.example';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');

for(const [name,source] of [['vercel',vercelSource],['cloudflare',cfSource]]){
  assert.ok(source.includes('const MAX_BODY_BYTES = 4 * 1024 * 1024')||source.includes('const MAX_BODY_BYTES=4 * 1024 * 1024'),name);
  assert.ok(source.includes('REQUEST_BODY_TOO_LARGE'),name);
  assert.ok(source.includes('BODY_TOO_LARGE'),name);
}
assert.ok(cfSource.includes('request.body.getReader()'));
assert.ok(cfSource.includes('reader.cancel()'));
assert.ok(!cfSource.includes('await request.text()'));

function makeRes(){const h=Object.create(null);return{statusCode:200,headers:h,body:'',setHeader(n,v){h[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(s){try{return JSON.parse(s);}catch{return null;}}

async function invokeVercel(body,extraHeaders={}){
  let calls=0; const oldFetch=global.fetch; const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=SECRET;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={'sec-fetch-site':'same-origin',origin:ORIGIN,host:'crm.example','x-forwarded-host':'crm.example','x-forwarded-proto':'https',...extraHeaders};
  const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{global.fetch=oldFetch;if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;}
  return{status:res.statusCode,json:parse(res.body),calls};
}

async function invokeCf(body,extraHeaders={}){
  let calls=0; const oldFetch=global.fetch;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});};
  const headers={'sec-fetch-site':'same-origin',origin:ORIGIN,'content-type':'application/json',...extraHeaders};
  const request=new Request(`${ORIGIN}/api/crm`,{method:'POST',headers,body});
  try{const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:SECRET}});return{status:response.status,json:parse(await response.text()),calls};}finally{global.fetch=oldFetch;}
}

const validObject={rpc:'crm_public_status',args:{probe:'x'.repeat(256 * 1024)}};
let result=await invokeVercel(validObject);
assert.equal(result.status,200);assert.equal(result.calls,1);
result=await invokeCf(JSON.stringify(validObject));
assert.equal(result.status,200);assert.equal(result.calls,1);

for(const invoke of [
  ()=>invokeVercel({rpc:'crm_public_status',args:{}},{'content-length':String(MAX+1)}),
  ()=>invokeCf(JSON.stringify({rpc:'crm_public_status',args:{}}),{'content-length':String(MAX+1)}),
]){
  result=await invoke();assert.equal(result.status,413);assert.equal(result.json?.message,'REQUEST_BODY_TOO_LARGE');assert.equal(result.calls,0);
}

const oversized=JSON.stringify({rpc:'crm_public_status',args:{padding:'x'.repeat(MAX)}});
assert.ok(Buffer.byteLength(oversized,'utf8')>MAX);
result=await invokeVercel(oversized);
assert.equal(result.status,413);assert.equal(result.json?.message,'REQUEST_BODY_TOO_LARGE');assert.equal(result.calls,0);
result=await invokeCf(oversized);
assert.equal(result.status,413);assert.equal(result.json?.message,'REQUEST_BODY_TOO_LARGE');assert.equal(result.calls,0);

console.log('CRM_API_BODY_LIMIT_OK: platforms=vercel+cloudflare; max=4MiB; declared-oversize=413+zero-fetch; actual-oversize=413+zero-fetch; cloudflare=stream-limited-before-full-buffer');
