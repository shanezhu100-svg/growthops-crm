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

// Execute saveClient together with the actual shipped pure helper chain it calls.
// Only durable/external side effects and the deterministic local-date clock are
// stubbed so this regression cannot bypass cleanPlatformAccounts/normalizeClient.
const sideEffects=new Set([
  'persist','logAudit','notify','navigateTo',
  'ensureAutomaticAssetCosts','ensureAutomaticReceivables','ensureClientFirstReceivable',
]);
const pureStubs=new Set(['localDateKey']);
const methodSources=new Map();
function collectMethod(name){
  if(methodSources.has(name)||sideEffects.has(name)||pureStubs.has(name))return;
  const source=extractMethod(name);
  methodSources.set(name,source);
  for(const match of source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)){
    const child=match[1];
    if(child!==name&&!sideEffects.has(child)&&!pureStubs.has(child))collectMethod(child);
  }
}
collectMethod('saveClient');

// Compile each shipped method independently. Concatenating independently extracted
// methods into one object literal is parser-fragile because neighboring method
// boundaries can carry syntax that is valid alone but ambiguous after reassembly.
// Independent compilation preserves each shipped method body and its runtime `this`
// semantics while avoiding any test-owned reimplementation of the helper logic.
const context={
  Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp,
  structuredClone:globalThis.structuredClone,
  crypto:globalThis.crypto,
  setTimeout:(fn)=>{if(typeof fn==='function')fn();return 1;},
  clearTimeout:()=>{},
};
const methods={};
for(const [name,source] of methodSources){
  try{
    const compiled=vm.runInNewContext(`({${source}})`,context,{timeout:1000});
    if(typeof compiled[name]!=='function')throw new Error('compiled member is not a function');
    methods[name]=compiled[name];
  }catch(error){
    throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: unable to compile shipped helper ${name}: ${error.message}; helpers=${[...methodSources.keys()].sort().join(',')}`);
  }
}
if(typeof methods.saveClient!=='function')throw new Error('BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: saveClient is not executable');

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
  id:'client-save-1',name:'Before Save',archived:false,status:'ACTIVE',platform:['TK'],
  monthlyFee:0,currency:'USD',networkEnvironments:[],
  fbAccounts:[],tkAccounts:[{id:'old-tk',bcId:'old-bc',adAccountId:'old-ad',loginAccount:'old-login'}],
  googleAccounts:[],instagramAccounts:[],
};
let persisted=0,audited=0,notified=0;
const calls=[];
const target={
  ...methods,
  clients:[existing],leads:[],
  form:{
    ...existing,
    name:'After Save',status:'ACTIVE',platform:['TK'],monthlyFee:0,currency:'USD',networkEnvironments:[],
    fbAccounts:[],tkAccounts:[syntheticTk],googleAccounts:[],instagramAccounts:[],
  },
  formDirty:true,
  selectedClientId:'client-save-1',selectedAssetsClientId:'client-save-1',selectedAdsClientId:'client-save-1',
  selectedAnalyticsClientId:'client-save-1',selectedSopClientId:'client-save-1',
  currentPage:'client-form',
  currentUser:{id:'synthetic-user',name:'Synthetic User',role:'ADMIN'},
  localDateKey:()=> '2026-09-01',
  persist:()=>{persisted+=1;calls.push('persist')},
  logAudit:(...args)=>{audited+=1;calls.push(['audit',...args])},
  notify:()=>{notified+=1},
  navigateTo:(...args)=>{calls.push(['navigateTo',...args])},
  ensureAutomaticAssetCosts:(...args)=>{calls.push(['ensureAutomaticAssetCosts',...args])},
  ensureAutomaticReceivables:(...args)=>{calls.push(['ensureAutomaticReceivables',...args])},
  ensureClientFirstReceivable:(...args)=>{calls.push(['ensureClientFirstReceivable',...args])},
  $nextTick:fn=>{if(typeof fn==='function')fn()},
};
const subject=new Proxy(target,{
  get(obj,prop){
    if(prop in obj)return obj[prop];
    return undefined;
  },
  set(obj,prop,value){obj[prop]=value;return true;},
});

let result;
try{
  result=methods.saveClient.call(subject);
  if(result&&typeof result.then==='function')await result;
}catch(error){
  const refs=[...new Set([...methodSources.values()].flatMap(source=>[...source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)/g)].map(match=>match[1])))].sort();
  throw new Error(`BUSINESS_CLIENT_TIKTOK_SAVE_FAILED: shipped saveClient/helper chain threw ${error?.name||'Error'}:${error?.message||error}; helpers=${[...methodSources.keys()].sort().join(',')}; this-refs=${refs.join(',')}`);
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

console.log(`BUSINESS_CLIENT_TIKTOK_SAVE_OK: source=final-shipped-saveClient+helpers; helpers=${[...methodSources.keys()].sort().join('+')}; tkAccounts=preserved; bcId+adAccountId+loginAccount=preserved; persist=${persisted}; audit=${audited}; notice=${notified}`);
