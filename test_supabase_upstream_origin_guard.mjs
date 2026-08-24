import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_upstream_origin_20260824';
const DEFAULT_URL='https://avahcwyxparbcjdfglzx.supabase.co';
const STAGING_URL='https://staging-project-ref.supabase.co';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return JSON.parse(text);}catch{return null;}}
const headers={'sec-fetch-site':'same-origin',origin:'https://crm.example',host:'crm.example','x-forwarded-host':'crm.example','x-forwarded-proto':'https'};
const body={rpc:'crm_public_status',args:{}};

async function invokeVercel(url,fetchImpl){
  const oldFetch=global.fetch;
  const names=['GROWTHOPS_SUPABASE_SECRET_KEY','GROWTHOPS_SUPABASE_URL','VERCEL_ENV'];
  const old=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
  if(url===undefined) delete process.env.GROWTHOPS_SUPABASE_URL; else process.env.GROWTHOPS_SUPABASE_URL=url;
  delete process.env.VERCEL_ENV;
  global.fetch=fetchImpl; const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{
    global.fetch=oldFetch;
    for(const name of names){if(old[name]===undefined)delete process.env[name];else process.env[name]=old[name];}
  }
  return{status:res.statusCode,json:parse(res.body)};
}
async function invokeCf(url,fetchImpl){
  const oldFetch=global.fetch; global.fetch=fetchImpl;
  const env={GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET}; if(url!==undefined)env.GROWTHOPS_SUPABASE_URL=url;
  const request=new Request('https://crm.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{const response=await cloudflareHandler({request,env});return{status:response.status,json:parse(await response.text())};}finally{global.fetch=oldFetch;}
}

for(const source of [vercelSource,cfSource]){
  assert.ok(source.includes('function supabaseOrigin('));
  assert.ok(source.includes("parsed.protocol !== 'https:'")||source.includes("parsed.protocol!=='https:'"));
  assert.ok(source.includes("host.endsWith('.supabase.co')"));
  assert.ok(source.includes('parsed.username'));
  assert.ok(source.includes('parsed.password'));
  assert.ok(source.includes('parsed.pathname'));
  assert.ok(source.includes('parsed.search'));
  assert.ok(source.includes('parsed.hash'));
  assert.ok(source.includes("redirect: 'error'")||source.includes("redirect:'error'"));
}

const invalid=[
  'http://staging-project-ref.supabase.co',
  'https://example.com',
  'https://staging-project-ref.supabase.co.evil.example',
  'https://user:pass@staging-project-ref.supabase.co',
  'https://staging-project-ref.supabase.co/rest/v1',
  'https://staging-project-ref.supabase.co/?redirect=https://evil.example',
  'https://staging-project-ref.supabase.co/#fragment',
  'not-a-url',
];
for(const url of invalid){
  for(const invoke of [invokeVercel,invokeCf]){
    let calls=0; const result=await invoke(url,async()=>{calls++;throw new Error('fetch must not run');});
    assert.equal(result.status,503,url); assert.equal(result.json?.message,'SERVER_IDENTITY_NOT_CONFIGURED',url); assert.equal(calls,0,url);
  }
}

for(const [input,expected] of [[undefined,DEFAULT_URL],[STAGING_URL+'/',STAGING_URL]]){
  for(const invoke of [invokeVercel,invokeCf]){
    let capture=null;
    const result=await invoke(input,async(url,options)=>{capture={url:String(url),apikey:options.headers.apikey,redirect:options.redirect};return new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});});
    assert.equal(result.status,200); assert.equal(capture.apikey,TEST_SECRET); assert.equal(capture.url,expected+'/rest/v1/rpc/crm_public_status'); assert.equal(capture.redirect,'error');
  }
}

console.log('SUPABASE_UPSTREAM_ORIGIN_GUARD_OK: platforms=vercel+cloudflare; scheme=https-only; host=*.supabase.co-only; credentials+path+query+fragment=denied; redirects=error; invalid-target=503+zero-fetch; staging-origin=allowed; vercel-env=isolated-non-production');
