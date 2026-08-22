import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_p5_group4_safe_summary';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const {onRequest:cloudflareHandler}=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parseJson(text){return text?JSON.parse(text):null;}
async function invokeVercel({headers,body},fetchImpl){
  const old=global.fetch;global.fetch=fetchImpl;const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{global.fetch=old;}
  return{status:res.statusCode,json:parseJson(res.body)};
}
async function invokeCloudflare({headers,body},fetchImpl){
  const old=global.fetch;global.fetch=fetchImpl;
  const request=new Request('https://preview.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET}});return{status:response.status,json:parseJson(await response.text())};}
  finally{global.fetch=old;}
}
const sameOrigin={'sec-fetch-site':'same-origin',origin:'https://preview.example',host:'preview.example','x-forwarded-host':'preview.example','x-forwarded-proto':'https'};
const rpc='crm_client_account_safe_summary';
const forgedArgs={p_token:'browser-forged-token',p_client_id:'client-safe-summary-test'};
const safeReply={clientId:'client-safe-summary-test',facebook:{loginAccount:'fb@example.test',hasPassword:true,has2FA:false},tiktok:{loginAccount:'',hasPassword:false,has2FA:false},googleAccounts:[],instagramAccounts:[]};

for(const invoke of [invokeVercel,invokeCloudflare]){
  let calls=0;
  const missing=await invoke({headers:sameOrigin,body:{rpc,args:forgedArgs}},async()=>{calls+=1;return new Response(JSON.stringify(safeReply),{status:200,headers:{'Content-Type':'application/json'}});});
  assert.equal(missing.status,401);
  assert.equal(missing.json.message,'SESSION_REQUIRED');
  assert.equal(calls,0,'safe-summary contacted upstream without an HttpOnly session');

  let requestUrl='';let upstreamBody=null;
  const present=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc,args:forgedArgs}},async(url,options)=>{calls+=1;requestUrl=String(url);upstreamBody=JSON.parse(options.body);return new Response(JSON.stringify(safeReply),{status:200,headers:{'Content-Type':'application/json'}});});
  assert.equal(present.status,200);
  assert.equal(calls,1);
  assert.ok(requestUrl.endsWith('/rest/v1/rpc/crm_client_account_safe_summary'));
  assert.equal(upstreamBody.p_token,'cookie-session-token');
  assert.equal(upstreamBody.p_client_id,'client-safe-summary-test');
  assert.deepEqual(present.json,safeReply);
}

console.log('P5_GROUP4_SAFE_SUMMARY_BFF_OK: no-session=401+zero-upstream; cookie-token=authoritative; both-platforms=pass');
