import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_p5_group5_session_state';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const {onRequest:cloudflareHandler}=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parseJson(text){try{return text?JSON.parse(text):null;}catch{return null;}}
async function invokeVercel({headers,body},fetchImpl){
  const old=global.fetch;global.fetch=fetchImpl;const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{global.fetch=old;}
  return{status:res.statusCode,headers:res.headers,json:parseJson(res.body)};
}
async function invokeCloudflare({headers,body},fetchImpl){
  const old=global.fetch;global.fetch=fetchImpl;
  const request=new Request('https://preview.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{
    const response=await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET}});
    return{status:response.status,headers:{'set-cookie':response.headers.get('set-cookie')},json:parseJson(await response.text())};
  }finally{global.fetch=old;}
}
const sameOrigin={'sec-fetch-site':'same-origin',origin:'https://preview.example',host:'preview.example','x-forwarded-host':'preview.example','x-forwarded-proto':'https'};

const cases=[
  {rpc:'crm_load_state_v3',args:{p_token:'browser-forged-token'},reply:{workspaceId:'w1',revision:11,state:{clients:[]},user:{id:'u1',role:'ADMIN'}}},
  {rpc:'crm_save_state',args:{p_token:'browser-forged-token',p_state:{clients:[]},p_expected_revision:11},reply:{revision:12,updatedAt:'2026-08-22T16:00:00Z'}},
  {rpc:'crm_logout',args:{p_token:'browser-forged-token'},reply:true},
];

for(const testCase of cases){
  for(const invoke of [invokeVercel,invokeCloudflare]){
    let calls=0;
    const missing=await invoke({headers:sameOrigin,body:{rpc:testCase.rpc,args:testCase.args}},async()=>{calls+=1;return new Response(JSON.stringify(testCase.reply),{status:200,headers:{'Content-Type':'application/json'}});});
    assert.equal(missing.status,401);
    assert.equal(missing.json.message,'SESSION_REQUIRED');
    assert.equal(calls,0,`${testCase.rpc} contacted upstream without session cookie`);

    let requestUrl='';let upstreamBody=null;
    const present=await invoke({headers:{...sameOrigin,cookie:'__Host-growthops_crm=cookie-session-token'},body:{rpc:testCase.rpc,args:testCase.args}},async(url,options)=>{calls+=1;requestUrl=String(url);upstreamBody=JSON.parse(options.body);return new Response(JSON.stringify(testCase.reply),{status:200,headers:{'Content-Type':'application/json'}});});
    assert.equal(present.status,200);
    assert.equal(calls,1);
    assert.ok(requestUrl.endsWith(`/rest/v1/rpc/${testCase.rpc}`));
    assert.equal(upstreamBody.p_token,'cookie-session-token');
    if(testCase.rpc==='crm_save_state'){
      assert.equal(upstreamBody.p_expected_revision,11);
      assert.deepEqual(upstreamBody.p_state,{clients:[]});
    }
    if(testCase.rpc==='crm_logout'){
      assert.match(String(present.headers['set-cookie']||''),/^__Host-growthops_crm=;/);
      assert.match(String(present.headers['set-cookie']||''),/Max-Age=0/);
    }
  }
}

console.log('P5_GROUP5_SESSION_STATE_BFF_OK: load+save+logout=no-session-zero-upstream; cookie-token=authoritative; logout-success=clears-cookie; both-platforms=pass');
