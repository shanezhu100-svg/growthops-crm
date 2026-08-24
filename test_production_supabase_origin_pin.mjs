import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_production_origin_pin_20260824';
const DEFAULT_URL='https://avahcwyxparbcjdfglzx.supabase.co';
const STAGING_URL='https://staging-project-ref.supabase.co';
const CF_PRODUCTION_HOST='growthops-crm.pages.dev';
const CF_PREVIEW_HOST='security-origin-pin.growthops-crm.pages.dev';
const UNKNOWN_HOST='local-origin-pin.example';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const {onRequest:cloudflareHandler}=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return JSON.parse(text);}catch{return null;}}
const body={rpc:'crm_public_status',args:{}};
const okResponse=()=>new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});

async function invokeVercel({environment,url,fetchImpl}){
  const oldFetch=global.fetch;
  const names=['GROWTHOPS_SUPABASE_SECRET_KEY','GROWTHOPS_SUPABASE_URL','VERCEL_ENV'];
  const old=Object.fromEntries(names.map(n=>[n,process.env[n]]));
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
  if(url===undefined)delete process.env.GROWTHOPS_SUPABASE_URL;else process.env.GROWTHOPS_SUPABASE_URL=url;
  if(environment===undefined)delete process.env.VERCEL_ENV;else process.env.VERCEL_ENV=environment;
  global.fetch=fetchImpl;
  const res=makeRes();
  const headers={'sec-fetch-site':'same-origin',origin:'https://origin-pin.example',host:'origin-pin.example','x-forwarded-host':'origin-pin.example','x-forwarded-proto':'https'};
  try{await vercelHandler({method:'POST',headers,body},res);}finally{
    global.fetch=oldFetch;
    for(const n of names){if(old[n]===undefined)delete process.env[n];else process.env[n]=old[n];}
  }
  return{status:res.statusCode,json:parse(res.body)};
}
async function invokeCloudflare({host,url,fetchImpl}){
  const oldFetch=global.fetch;global.fetch=fetchImpl;
  const env={GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET};if(url!==undefined)env.GROWTHOPS_SUPABASE_URL=url;
  const request=new Request(`https://${host}/api/crm`,{method:'POST',headers:{'sec-fetch-site':'same-origin',origin:`https://${host}`},body:JSON.stringify(body)});
  try{const response=await cloudflareHandler({request,env});return{status:response.status,json:parse(await response.text())};}finally{global.fetch=oldFetch;}
}

for(const [label,source,markers] of [
  ['Vercel',vercelSource,["isProduction = environment === 'production'",'isProduction && url !== SUPABASE_URL_DEFAULT']],
  ['Cloudflare',cfSource,['isPagesProduction=requestHost===CLOUDFLARE_PRODUCTION_HOST','isPagesProduction&&url!==SUPABASE_URL_DEFAULT']],
])for(const marker of markers)assert.ok(source.includes(marker),`${label} missing production pin marker ${marker}`);

for(const scenario of [
  {name:'vercel-production-staging-denied',invoke:invokeVercel,args:{environment:'production',url:STAGING_URL}},
  {name:'cloudflare-production-staging-denied',invoke:invokeCloudflare,args:{host:CF_PRODUCTION_HOST,url:STAGING_URL}},
]){
  let calls=0;const result=await scenario.invoke({...scenario.args,fetchImpl:async()=>{calls++;throw new Error('misdirected production secret must not fetch');}});
  assert.equal(result.status,503,scenario.name);assert.equal(result.json?.message,'SERVER_IDENTITY_NOT_CONFIGURED',scenario.name);assert.equal(calls,0,scenario.name);
}

for(const scenario of [
  {name:'vercel-production-default',invoke:invokeVercel,args:{environment:'production'}},
  {name:'vercel-production-explicit-canonical',invoke:invokeVercel,args:{environment:'production',url:DEFAULT_URL}},
  {name:'cloudflare-production-default',invoke:invokeCloudflare,args:{host:CF_PRODUCTION_HOST}},
  {name:'cloudflare-production-explicit-canonical',invoke:invokeCloudflare,args:{host:CF_PRODUCTION_HOST,url:DEFAULT_URL}},
]){
  let captured='';const result=await scenario.invoke({...scenario.args,fetchImpl:async url=>{captured=String(url);return okResponse();}});
  assert.equal(result.status,200,scenario.name);assert.equal(captured,`${DEFAULT_URL}/rest/v1/rpc/crm_public_status`,scenario.name);
}

for(const scenario of [
  {name:'vercel-preview-staging-preserved',invoke:invokeVercel,args:{environment:'preview',url:STAGING_URL}},
  {name:'cloudflare-preview-staging-preserved',invoke:invokeCloudflare,args:{host:CF_PREVIEW_HOST,url:STAGING_URL}},
  {name:'cloudflare-unknown-local-staging-preserved',invoke:invokeCloudflare,args:{host:UNKNOWN_HOST,url:STAGING_URL}},
]){
  let captured='';const result=await scenario.invoke({...scenario.args,fetchImpl:async url=>{captured=String(url);return okResponse();}});
  assert.equal(result.status,200,scenario.name);assert.equal(captured,`${STAGING_URL}/rest/v1/rpc/crm_public_status`,scenario.name);
}

console.log('PRODUCTION_SUPABASE_ORIGIN_PIN_OK: vercel-production=canonical-only; cloudflare-pages-production=canonical-only; staging-in-production=503+zero-fetch; preview-staging=preserved; local-unknown-host=preserved');
