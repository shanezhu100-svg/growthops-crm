import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET='sb_secret_test_trusted_login_source';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY=TEST_SECRET;
const require=createRequire(import.meta.url);
const vercelHandler=require('./api/crm.js');
const cfSource=readFileSync(new URL('./functions/api/crm.js',import.meta.url),'utf8');
const {onRequest:cloudflareHandler}=await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

function bucket(ip){return createHash('sha256').update(String(ip).trim().toLowerCase(),'utf8').digest('hex').slice(0,24);}
function makeRes(){const headers=Object.create(null);return{statusCode:200,headers,body:'',setHeader(n,v){headers[String(n).toLowerCase()]=String(v);},end(v=''){this.body=String(v);}};}
function ok(data){return Promise.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}));}
function loginData(){return{token:'server-session-token',workspaceId:'w1',revision:1,user:{id:'u1',role:'ADMIN'},state:{}};}

async function invokeVercel(headers,body,fetchImpl){
  const oldFetch=global.fetch;global.fetch=fetchImpl;const res=makeRes();
  try{await vercelHandler({method:'POST',headers,body},res);}finally{global.fetch=oldFetch;}
  return res;
}
async function invokeCloudflare(headers,body,fetchImpl){
  const oldFetch=global.fetch;global.fetch=fetchImpl;
  const request=new Request('https://preview.example/api/crm',{method:'POST',headers,body:JSON.stringify(body)});
  try{return await cloudflareHandler({request,env:{GROWTHOPS_SUPABASE_SECRET_KEY:TEST_SECRET}});}finally{global.fetch=oldFetch;}
}

const base={'sec-fetch-site':'same-origin',origin:'https://preview.example',host:'preview.example','x-forwarded-host':'preview.example','x-forwarded-proto':'https'};
const spoof='ffffffffffffffffffffffff';

{
  const trusted='203.0.113.7';let upstreamHeaders=null;let upstreamBody=null;
  await invokeVercel({...base,'x-forwarded-for':`${trusted}, 10.0.0.1`,'cf-connecting-ip':'198.51.100.99','x-growthops-source-bucket':spoof},{rpc:'crm_login_v3',args:{p_username:'test-user',p_password:'not-a-real-password'}},async(_url,options)=>{upstreamHeaders=options.headers;upstreamBody=JSON.parse(options.body);return ok(loginData());});
  assert.equal(upstreamHeaders['x-growthops-source-bucket'],bucket(trusted));
  assert.notEqual(upstreamHeaders['x-growthops-source-bucket'],spoof);
  assert.equal(upstreamHeaders['x-forwarded-for'],undefined);
  assert.equal(upstreamHeaders['cf-connecting-ip'],undefined);
  assert.equal(upstreamBody.p_username,'test-user');
  assert.equal(upstreamBody.p_password,'not-a-real-password');
  assert.equal(upstreamBody['x-growthops-source-bucket'],undefined);
  assert.doesNotMatch(JSON.stringify(upstreamHeaders),new RegExp(trusted.replaceAll('.','\\.')));
}

{
  const trusted='198.51.100.9';let upstreamHeaders=null;let upstreamBody=null;
  await invokeCloudflare({...base,'cf-connecting-ip':trusted,'x-forwarded-for':'203.0.113.88','x-growthops-source-bucket':spoof},{rpc:'crm_login_v3',args:{p_username:'test-user',p_password:'not-a-real-password'}},async(_url,options)=>{upstreamHeaders=options.headers;upstreamBody=JSON.parse(options.body);return ok(loginData());});
  assert.equal(upstreamHeaders['x-growthops-source-bucket'],bucket(trusted));
  assert.notEqual(upstreamHeaders['x-growthops-source-bucket'],spoof);
  assert.equal(upstreamHeaders['x-forwarded-for'],undefined);
  assert.equal(upstreamHeaders['cf-connecting-ip'],undefined);
  assert.equal(upstreamBody['x-growthops-source-bucket'],undefined);
  assert.doesNotMatch(JSON.stringify(upstreamHeaders),new RegExp(trusted.replaceAll('.','\\.')));
}

for(const [name,invoke,headers] of [
  ['vercel',invokeVercel,{...base,'x-forwarded-for':'203.0.113.7'}],
  ['cloudflare',invokeCloudflare,{...base,'cf-connecting-ip':'198.51.100.9'}],
]){
  let upstreamHeaders=null;
  await invoke(headers,{rpc:'crm_public_status',args:{}},async(_url,options)=>{upstreamHeaders=options.headers;return ok({initialized:true});});
  assert.equal(upstreamHeaders['x-growthops-source-bucket'],undefined,`${name} must send source bucket only for login`);
}

{
  let upstreamHeaders=null;
  await invokeVercel({...base,'x-forwarded-for':'not-an-ip','x-growthops-source-bucket':spoof},{rpc:'crm_login_v3',args:{p_username:'x',p_password:'y'}},async(_url,options)=>{upstreamHeaders=options.headers;return ok(loginData());});
  assert.equal(upstreamHeaders['x-growthops-source-bucket'],undefined);
}
{
  let upstreamHeaders=null;
  await invokeCloudflare({...base,'cf-connecting-ip':'not-an-ip','x-growthops-source-bucket':spoof},{rpc:'crm_login_v3',args:{p_username:'x',p_password:'y'}},async(_url,options)=>{upstreamHeaders=options.headers;return ok(loginData());});
  assert.equal(upstreamHeaders['x-growthops-source-bucket'],undefined);
}

console.log('POST_P5_LOGIN_TRUSTED_SOURCE_BUCKET_OK: vercel=x-forwarded-for-edge-trust; cloudflare=cf-connecting-ip-edge-trust; outbound=sha256-24hex-only; spoofed-bucket=ignored; raw-ip=not-forwarded; non-login=no-bucket');
