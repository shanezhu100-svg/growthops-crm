import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const source=extractMethod('saveClient');
let saveClient;
try{
  ({saveClient}=vm.runInNewContext(`({${source}})`,{
    Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,
    structuredClone:globalThis.structuredClone,
    setTimeout:(fn)=>{if(typeof fn==='function')fn();return 1;},
    clearTimeout:()=>{},
  },{timeout:1000}));
}catch(error){
  throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: unable to compile shipped saveClient: ${error.message}`);
}
if(typeof saveClient!=='function')throw new Error('BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: saveClient is not executable');

const fail=message=>{throw new Error('BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};

const syntheticTk={
  id:'tk-save-1',
  name:'Synthetic TikTok',
  accountId:'tk-account-save-1',
  bcId:'bc-save-1',
  adAccountId:'ad-save-1',
  loginAccount:'tk-login-save',
  loginPassword:'',
  twofa:'',
};
const existing={
  id:'client-save-1',name:'Before Save',archived:false,
  fbAccounts:[],tkAccounts:[{id:'old-tk',bcId:'old-bc',adAccountId:'old-ad',loginAccount:'old-login'}],
  googleAccounts:[],instagramAccounts:[],
};
let persisted=0,audited=0,notified=0;
const calls=[];
const target={
  clients:[existing],
  form:{
    id:'client-save-1',name:'After Save',status:'ACTIVE',platform:['TK'],
    fbAccounts:[],tkAccounts:[syntheticTk],googleAccounts:[],instagramAccounts:[],
  },
  clientForm:null,
  editingClient:existing,
  editingClientId:'client-save-1',
  editClientId:'client-save-1',
  selectedClientId:'client-save-1',
  currentPage:'client-form',
  currentUser:{id:'synthetic-user',name:'Synthetic User',role:'ADMIN'},
  persist:()=>{persisted+=1;calls.push('persist')},
  logAudit:(...args)=>{audited+=1;calls.push(['audit',...args])},
  notify:()=>{notified+=1},
  newId:()=> 'synthetic-generated-id',
  generateId:()=> 'synthetic-generated-id',
  uid:()=> 'synthetic-generated-id',
  $nextTick:fn=>{if(typeof fn==='function')fn()},
};
target.clientForm=target.form;

const neutralHelpers=new Set([
  'closeClientForm','resetClientForm','resetAssetPager','syncAnalyticsAccountSelection','syncAdsAccountSelection',
  'syncSopAccountSelection','refreshAccountSafeSummary','refreshCredentialStatus','clearReveal','clearCredentialReveal',
]);
const identityHelpers=new Set(['normalizeClient','normalizeClientForm','sanitizeClient','sanitizeClientForm']);
const subject=new Proxy(target,{
  get(obj,prop){
    if(prop in obj)return obj[prop];
    if(typeof prop==='string'&&neutralHelpers.has(prop))return (...args)=>{calls.push([prop,...args]);};
    if(typeof prop==='string'&&identityHelpers.has(prop))return value=>value;
    return undefined;
  },
  set(obj,prop,value){obj[prop]=value;return true;},
});

let result;
try{
  result=saveClient.call(subject);
  if(result&&typeof result.then==='function')await result;
}catch(error){
  const refs=[...new Set([...source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)/g)].map(match=>match[1]))].sort();
  throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: shipped saveClient threw ${error?.name||'Error'}:${error?.message||error}; this-refs=${refs.join(',')}`);
}

const saved=subject.clients.find(client=>
  Array.isArray(client?.tkAccounts)&&client.tkAccounts.some(account=>String(account?.id??'')==='tk-save-1')
);
if(!saved)fail('saved clients collection does not retain synthetic TikTok account');
eq(saved.name,'After Save','edited client name persisted alongside TikTok account');
const account=saved.tkAccounts.find(item=>String(item?.id??'')==='tk-save-1');
eq(account.bcId,'bc-save-1','TikTok BC ID preserved by saveClient');
eq(account.adAccountId,'ad-save-1','TikTok ad account ID preserved by saveClient');
eq(account.loginAccount,'tk-login-save','TikTok login account preserved by saveClient');
if(account.loginPassword&&String(account.loginPassword).trim())fail('synthetic blank TikTok password unexpectedly became non-empty');
if(account.twofa&&String(account.twofa).trim())fail('synthetic blank TikTok 2FA unexpectedly became non-empty');
eq(persisted,1,'saveClient persists exactly once');
eq(audited,1,'saveClient audits exactly once');

console.log(`BUSINESS_CLIENT_TIKTOK_SAVE_OK: source=final-shipped-saveClient; tkAccounts=preserved; bcId+adAccountId+loginAccount=preserved; persist=${persisted}; audit=${audited}; notice=${notified}`);
