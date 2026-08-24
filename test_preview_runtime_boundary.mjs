import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_preview_runtime_boundary_20260824';
const DEFAULT_URL='https://avahcwyxparbcjdfglzx.supabase.co';
const STAGING_URL='https://staging-project-ref.supabase.co';
const CF_PRODUCTION_HOST='growthops-crm.pages.dev';
const CF_HASH_PREVIEW_HOST='373f31e2.growthops-crm.pages.dev';
const CF_BRANCH_PREVIEW_HOST='security-preview-runtime-boundary.growthops-crm.pages.dev';
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const vercelSource=readFileSync(new URL('./api/crm.js',import.meta.url),'utf8');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const cfModule=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler=cfModule.onRequest;

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parse(text){try{return JSON.parse(text);}catch{return null;}}
const vercelHeaders={'sec-fetch-site':'same-origin',origin:'https://crm.example',host:'crm.example','x-forwarded-host':'crm.example','x-forwarded-proto':'https'};
const body={rpc:'crm_public_status',args:{}};
const okResponse=()=>new Response(JSON.stringify({service:'GrowthOps CRM Cloud'}),{status:200,headers:{'Content-Type':'application/json'}});

async function invokeVercel({environment='preview',url,fetchImpl}){
  const oldFetch=global.fetch;
  const names=['GROWTHOPS_SUPABASE_SECRET_KEY','GROWTHOPS_SUPABASE_URL','VERCEL_ENV'];
  const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
  if(url===undefined)delete process.env.GROWTHOPS_SUPABASE_URL;else process.env.GROWTHOPS_SUPABASE_URL=url;
  if(environment===undefined)delete process.env.VERCEL_ENV;else process.env.VERCEL_ENV=environment;
  global.fetch=fetchImpl;
  const res=makeRes();
  try{await vercelHandler({method:'POST',headers:vercelHeaders,body},res);}finally{
    global.fetch=oldFetch;
    for(const name of names){if(previous[name]===undefined)delete process.env[name];else process.env[name]=previous[name];}
  }
  return{status:res.statusCode,json:parse(res.body)};
}

async function invokeCloudflare({host=CF_HASH_PREVIEW_HOST,url,fetchImpl}){
  const oldFetch=global.fetch;global.fetch=fetchImpl;
  const env={GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET};
  if(url!==undefined)env.GROWTHOPS_SUPABASE_URL=url;
  const request=new Request(`https://${host}/api/crm`,{method:'POST',headers:{'sec-fetch-site':'same-origin',origin:`https://${host}`},body:JSON.stringify(body)});
  try{const response=await cloudflareHandler({request,env});return{status:response.status,json:parse(await response.text())};}finally{global.fetch=oldFetch;}
}

for(const [label,source,markers] of [
  ['Vercel',vercelSource,['VERCEL_ENV',"=== 'preview'",'SUPABASE_URL_DEFAULT']],
  ['Cloudflare',cfSource,['CLOUDFLARE_PRODUCTION_HOST',CF_PRODUCTION_HOST,'requestHost.endsWith(`.${CLOUDFLARE_PRODUCTION_HOST}`)','serverConfig(env,request.url)','SUPABASE_URL_DEFAULT']],
]){
  for(const marker of markers)assert.ok(source.includes(marker),`${label} missing runtime preview marker ${marker}`);
}
assert.ok(!cfSource.includes('CF_PAGES_BRANCH'),'Cloudflare runtime boundary must not depend on CF_PAGES_BRANCH');

for(const scenario of [
  {name:'vercel-preview-no-url',invoke:invokeVercel,args:{environment:'preview'}},
  {name:'vercel-preview-production-url',invoke:invokeVercel,args:{environment:'preview',url:DEFAULT_URL}},
  {name:'cloudflare-hash-preview-no-url',invoke:invokeCloudflare,args:{host:CF_HASH_PREVIEW_HOST}},
  {name:'cloudflare-branch-preview-production-url',invoke:invokeCloudflare,args:{host:CF_BRANCH_PREVIEW_HOST,url:DEFAULT_URL}},
]){
  let calls=0;
  const result=await scenario.invoke({...scenario.args,fetchImpl:async()=>{calls++;throw new Error('fetch must not run');}});
  assert.equal(result.status,503,scenario.name);
  assert.equal(result.json?.message,'SERVER_IDENTITY_NOT_CONFIGURED',scenario.name);
  assert.equal(calls,0,scenario.name);
}

for(const scenario of [
  {name:'vercel-preview-staging',invoke:invokeVercel,args:{environment:'preview',url:STAGING_URL}},
  {name:'cloudflare-hash-preview-staging',invoke:invokeCloudflare,args:{host:CF_HASH_PREVIEW_HOST,url:STAGING_URL}},
  {name:'cloudflare-branch-preview-staging',invoke:invokeCloudflare,args:{host:CF_BRANCH_PREVIEW_HOST,url:STAGING_URL}},
]){
  let captured='';
  const result=await scenario.invoke({...scenario.args,fetchImpl:async url=>{captured=String(url);return okResponse();}});
  assert.equal(result.status,200,scenario.name);
  assert.equal(captured,`${STAGING_URL}/rest/v1/rpc/crm_public_status`,scenario.name);
}

for(const scenario of [
  {name:'vercel-production-default',invoke:invokeVercel,args:{environment:'production'}},
  {name:'cloudflare-production-default',invoke:invokeCloudflare,args:{host:CF_PRODUCTION_HOST}},
]){
  let captured='';
  const result=await scenario.invoke({...scenario.args,fetchImpl:async url=>{captured=String(url);return okResponse();}});
  assert.equal(result.status,200,scenario.name);
  assert.equal(captured,`${DEFAULT_URL}/rest/v1/rpc/crm_public_status`,scenario.name);
}

console.log('PREVIEW_RUNTIME_BOUNDARY_OK: vercel-preview=no-default-prod; cloudflare-hash+branch-preview=no-default-prod; explicit-production-origin=denied-in-preview; explicit-staging-origin=allowed; production-default=preserved; denied-path=503+zero-fetch; CF_PAGES_BRANCH=not-required');
