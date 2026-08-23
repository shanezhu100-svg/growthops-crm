import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_p5_group6_public_boundary';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const {onRequest:cloudflareHandler}=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function parseJson(text){try{return text?JSON.parse(text):null;}catch{return null;}}
async function invokeVercel({headers,body,secret=TEST_SECRET},fetchImpl){
  const oldFetch=global.fetch;const oldSecret=process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  if(secret===null) delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY; else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=secret;
  global.fetch=fetchImpl;const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{global.fetch=oldFetch;if(oldSecret===undefined)delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;else process.env.GROWTHOPS_SUPABASE_SECRET_KEY=oldSecret;}
  return{status:res.statusCode,headers:res.headers,json:parseJson(res.body)};
}
async function invokeCloudflare({headers,body,secret=TEST_SECRET},fetchImpl){
  const oldFetch=global.fetch;global.fetch=fetchImpl;
  const request=new Request('https://preview.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{
    const response=await cloudflareHandler({request,env:secret===null?{}:{GROWTHOPS_SUPABASE_SECRET_KEY:secret}});
    return{status:response.status,headers:{'set-cookie':response.headers.get('set-cookie'),'cache-control':response.headers.get('cache-control')},json:parseJson(await response.text())};
  }finally{global.fetch=oldFetch;}
}
const sameOrigin={'sec-fetch-site':'same-origin',origin:'https://preview.example',host:'preview.example','x-forwarded-host':'preview.example','x-forwarded-proto':'https'};
function ok(data){return Promise.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}));}

for(const invoke of [invokeVercel,invokeCloudflare]){
  let calls=0;let requestUrl='';let requestBody=null;let requestHeaders=null;
  const statusResult=await invoke({headers:sameOrigin,body:{rpc:'crm_public_status',args:{p_token:'browser-forged-token'}}},async(url,options)=>{
    calls+=1;requestUrl=String(url);requestBody=JSON.parse(options.body);requestHeaders=options.headers;
    return ok({initialized:true,service:'GrowthOps CRM Cloud'});
  });
  assert.equal(statusResult.status,200);
  assert.equal(calls,1);
  assert.ok(requestUrl.endsWith('/rest/v1/rpc/crm_public_status'));
  assert.equal(requestBody.p_token,undefined);
  assert.equal(requestHeaders.apikey,TEST_SECRET);
  assert.equal(requestHeaders.Authorization,undefined);
  assert.deepEqual(statusResult.json,{initialized:true,service:'GrowthOps CRM Cloud'});
  assert.equal(statusResult.headers['set-cookie']??null,null);
  assert.match(String(statusResult.headers['cache-control']||''),/no-store/);

  calls=0;requestUrl='';requestBody=null;requestHeaders=null;
  const loginResult=await invoke({headers:sameOrigin,body:{rpc:'crm_login_v3',args:{p_username:'admin-example',p_password:'test-password-not-real',p_token:'browser-forged-token'}}},async(url,options)=>{
    calls+=1;requestUrl=String(url);requestBody=JSON.parse(options.body);requestHeaders=options.headers;
    return ok({token:'server-session-token',workspaceId:'w1',revision:4,user:{id:'u1',role:'ADMIN'},state:{clients:[]}});
  });
  assert.equal(loginResult.status,200);
  assert.equal(calls,1);
  assert.ok(requestUrl.endsWith('/rest/v1/rpc/crm_login_v3'));
  assert.equal(requestBody.p_username,'admin-example');
  assert.equal(requestBody.p_password,'test-password-not-real');
  assert.equal(requestBody.p_token,undefined);
  assert.equal(requestHeaders.apikey,TEST_SECRET);
  assert.equal(Object.prototype.hasOwnProperty.call(loginResult.json,'token'),false);
  const cookie=String(loginResult.headers['set-cookie']||'');
  assert.match(cookie,/^__Host-growthops_crm=server-session-token;/);
  assert.match(cookie,/Max-Age=604800/);
  assert.match(cookie,/HttpOnly/);
  assert.match(cookie,/Secure/);
  assert.match(cookie,/SameSite=Strict/);

  const bad=await invoke({headers:sameOrigin,body:{rpc:'crm_login_v3',args:{p_username:'unknown-example',p_password:'wrong-test-value'}}},()=>ok({error:'INVALID_CREDENTIALS'}));
  assert.equal(bad.status,401);
  assert.deepEqual(bad.json,{message:'LOGIN_FAILED'});
  assert.equal(bad.headers['set-cookie']??null,null);

  const missingToken=await invoke({headers:sameOrigin,body:{rpc:'crm_login_v3',args:{p_username:'admin-example',p_password:'test-password-not-real'}}},()=>ok({revision:4,user:{id:'u1',role:'ADMIN'},state:{}}));
  assert.equal(missingToken.status,502);
  assert.deepEqual(missingToken.json,{message:'LOGIN_SESSION_MISSING'});
  assert.equal(missingToken.headers['set-cookie']??null,null);

  for(const rpc of ['crm_public_status','crm_login_v3']){
    let upstreamCalls=0;
    const blocked=await invoke({headers:{...sameOrigin,'sec-fetch-site':'cross-site'},body:{rpc,args:rpc==='crm_login_v3'?{p_username:'x',p_password:'y'}:{}}},async()=>{upstreamCalls+=1;return ok({});});
    assert.equal(blocked.status,403);
    assert.equal(blocked.json.message,'CROSS_ORIGIN_REQUEST_BLOCKED');
    assert.equal(upstreamCalls,0);
  }

  for(const rpc of ['crm_public_status','crm_login_v3']){
    let upstreamCalls=0;
    const missingIdentity=await invoke({headers:sameOrigin,body:{rpc,args:rpc==='crm_login_v3'?{p_username:'x',p_password:'y'}:{}},secret:null},async()=>{upstreamCalls+=1;return ok({});});
    assert.equal(missingIdentity.status,503);
    assert.equal(missingIdentity.json.message,'SERVER_IDENTITY_NOT_CONFIGURED');
    assert.equal(upstreamCalls,0);
  }
}

console.log('P5_GROUP6_PUBLIC_BOUNDARY_BFF_OK: public-status=no-session+server-identity; login=no-session+token-to-HttpOnly-cookie; forged-token=stripped; invalid-login=generic; cross-origin=blocked; both-platforms=pass');
