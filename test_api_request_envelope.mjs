import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const SECRET='sb_secret_test_request_envelope_20260824';
const ORIGIN='https://crm.example';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes("Symbol('INVALID_JSON')"));
  assert.ok(source.includes('INVALID_REQUEST'));
  assert.ok(source.includes('Array.isArray(body)'));
}

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return JSON.parse(text);}catch{return null;}}
const baseHeaders={'sec-fetch-site':'same-origin',origin:ORIGIN,host:'crm.example','x-forwarded-host':'crm.example','x-forwarded-proto':'https','content-type':'application/json'};

async function invokeVercel(body){
  let calls=0;const oldFetch=global.fetch;const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=SECRET;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});};
  const res=makeRes();
  try{await vercelHandler({method:'POST',headers:baseHeaders,body},res);}finally{global.fetch=oldFetch;if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;}
  return{status:res.statusCode,json:parse(res.body),calls};
}

async function invokeCf(rawBody){
  let calls=0;const oldFetch=global.fetch;
  global.fetch=async()=>{calls++;return new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});};
  const request=new Request(`${ORIGIN}/api/crm`,{method:'POST',headers:baseHeaders,body:rawBody});
  try{const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:SECRET}});return{status:response.status,json:parse(await response.text()),calls};}finally{global.fetch=oldFetch;}
}

const invalidEnvelopes=[
  {vercel:[],cloudflare:'[]'},
  {vercel:'"string"',cloudflare:'"string"'},
  {vercel:'123',cloudflare:'123'},
  {vercel:'true',cloudflare:'true'},
  {vercel:null,cloudflare:'null'},
];
for(const sample of invalidEnvelopes){
  const v=await invokeVercel(sample.vercel);const c=await invokeCf(sample.cloudflare);
  for(const result of [v,c]){assert.equal(result.status,400);assert.deepEqual(result.json,{message:'INVALID_REQUEST'});assert.equal(result.calls,0);}
}

{
  const v=await invokeVercel('{');const c=await invokeCf('{');
  for(const result of [v,c]){assert.equal(result.status,400);assert.deepEqual(result.json,{message:'INVALID_JSON'});assert.equal(result.calls,0);}
}

{
  const v=await invokeVercel({});const c=await invokeCf('{}');
  for(const result of [v,c]){assert.equal(result.status,403);assert.deepEqual(result.json,{message:'RPC_NOT_ALLOWED'});assert.equal(result.calls,0);}
}

{
  const valid={rpc:'crm_public_status',args:{}};
  const v=await invokeVercel(valid);const c=await invokeCf(JSON.stringify(valid));
  for(const result of [v,c]){assert.equal(result.status,200);assert.equal(result.calls,1);}
}

console.log('CRM_API_REQUEST_ENVELOPE_OK: platforms=vercel+cloudflare; top-level=object-only; scalar+array+null=400+zero-fetch; malformed-json=400+zero-fetch; rpc-allowlist=preserved');
