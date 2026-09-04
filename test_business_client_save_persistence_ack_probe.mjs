import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const open=tail.indexOf('{');
  for(let cursor=open+1;cursor<tail.length;cursor+=1){
    if(tail[cursor]!=='}')continue;
    const source=tail.slice(0,cursor+1).trim();
    try{const parsed=vm.runInNewContext(`({${source}})`,Object.create(null),{timeout:100});if(typeof parsed?.[name]==='function')return source}catch{}
  }
  throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: ${name} boundary missing`);
}

const sideEffects=new Set(['persist','logAudit','notify','navigateTo','ensureAutomaticAssetCosts','ensureAutomaticReceivables','ensureClientFirstReceivable']);
const pureStubs=new Set(['localDateKey']);
const methodSources=new Map();
function collectMethod(name){
  if(methodSources.has(name)||sideEffects.has(name)||pureStubs.has(name))return;
  const source=extractMethod(name);methodSources.set(name,source);
  for(const match of source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)){
    const child=match[1];if(child!==name&&!sideEffects.has(child)&&!pureStubs.has(child))collectMethod(child);
  }
}
collectMethod('saveClient');
const context={Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp,structuredClone,crypto,setTimeout,clearTimeout};
const methods={};
for(const [name,source] of methodSources){const parsed=vm.runInNewContext(`({${source}})`,context,{timeout:1000});methods[name]=parsed[name]}
if(typeof methods.saveClient!=='function')throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: saveClient not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_CLIENT_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

function makeRuntime({kind,first}){
  const calls={fetch:[],notify:[],navigate:[],hooks:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#client-form'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  const existing={id:'client-save-1',name:'Before Save',archived:false,status:'ACTIVE',platform:['TK'],billingMode:'FULL_MONTH',monthlyFee:100,currency:'USD',startDate:'2026-09-01',networkEnvironments:[],fbAccounts:[],tkAccounts:[{id:'old-tk'}],googleAccounts:[],instagramAccounts:[]};
  const lead={id:'lead-source',company:'Lead Source',stage:'QUALIFIED',nextFollowUp:'2026-09-10',convertedClientId:null,convertedAt:''};
  const baseForm=kind==='edit'?{...existing,name:'After Edit',monthlyFee:120}:{id:null,sourceLeadId:'lead-source',name:'Created Client',archived:false,status:'ACTIVE',platform:['TK'],billingMode:'FULL_MONTH',monthlyFee:500,currency:'USD',startDate:'2026-09-01',networkEnvironments:[],fbAccounts:[],tkAccounts:[{id:'tk-new',bcId:'bc-new',adAccountId:'ad-new',loginAccount:'login-new',loginPassword:'',twofa:''}],googleAccounts:[],instagramAccounts:[]};
  Object.assign(subject,methods,{
    clients:kind==='edit'?[clone(existing)]:[],leads:[lead],financeReceivables:[],financeCosts:[],openingProviders:[],openingDeals:[],auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    form:clone(baseForm),formDirty:true,currentPage:'client-form',currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},
    selectedClientId:kind==='edit'?'client-save-1':null,selectedAssetsClientId:null,selectedAdsClientId:null,selectedAnalyticsClientId:null,selectedSopClientId:null,
    localDateKey:()=> '2026-09-01',$nextTick:fn=>{if(typeof fn==='function')fn()},ensureDailyBackup:()=>{},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),navigateTo:p=>calls.navigate.push(String(p)),
    ensureClientFirstReceivable:client=>{calls.hooks.push('first');subject.financeReceivables.push({id:`first-${client.id}`,clientId:client.id,source:'FIRST'});return 1},
    ensureAutomaticReceivables:client=>{calls.hooks.push('receivable');subject.financeReceivables.push({id:`auto-r-${client.id}`,clientId:client.id,source:'AUTO'});return 1},
    ensureAutomaticAssetCosts:client=>{calls.hooks.push('cost');subject.financeCosts.push({id:`auto-c-${client.id}`,clientId:client.id,source:'AUTO'});return 1},
    collectBackupPayload:()=>({clients:clone(subject.clients),leads:clone(subject.leads),financeReceivables:clone(subject.financeReceivables),financeCosts:clone(subject.financeCosts),openingProviders:[],openingDeals:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,existing,lead,resolveFirst:status=>gate?.resolve(response(status))};
}

const findings=[];const finding=x=>findings.push(x);
const successUi=calls=>calls.navigate.includes('client-detail')||calls.notify.some(m=>/保存|创建|更新|客户/.test(m));
const savedClient=(subject,kind)=>kind==='edit'?subject.clients.find(c=>String(c.id)==='client-save-1'):subject.clients.find(c=>c.name==='Created Client');
const failedStatePresent=(subject,kind)=>{
  const c=savedClient(subject,kind);if(!c)return false;
  const linked=subject.financeReceivables.some(x=>String(x.clientId)===String(c.id))||subject.financeCosts.some(x=>String(x.clientId)===String(c.id));
  const audit=subject.auditLogs.length>0;
  const leadChanged=kind==='create'?subject.leads[0]?.stage==='WON'&&String(subject.leads[0]?.convertedClientId||'')===String(c.id):true;
  return linked&&audit&&leadChanged&&(kind==='create'||c.name==='After Edit');
};

for(const kind of ['create','edit']){
  const {subject,calls,resolveFirst}=makeRuntime({kind,first:'deferred'});
  const task=subject.saveClient();await sleep(210);
  if(calls.fetch.length===1&&successUi(calls))finding(`${kind}-success-before-ack`);
  resolveFirst(200);if(task&&typeof task.then==='function')await task;await sleep(20);
}
for(const kind of ['create','edit']){
  const {subject,calls}=makeRuntime({kind,first:'fail'});
  const task=subject.saveClient();if(task&&typeof task.then==='function')await task;await sleep(240);
  if(failedStatePresent(subject,kind))finding(`${kind}-failed-save-local-state-remains`);
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const c=kind==='edit'?(later.clients||[]).find(x=>String(x.id)==='client-save-1'):(later.clients||[]).find(x=>x.name==='Created Client');
  const linked=c&&((later.financeReceivables||[]).some(x=>String(x.clientId)===String(c.id))||(later.financeCosts||[]).some(x=>String(x.clientId)===String(c.id)));
  const audit=(later.auditLogs||[]).length>0;
  const leadChanged=kind==='create'?(later.leads||[]).some(x=>x.id==='lead-source'&&x.stage==='WON'&&String(x.convertedClientId||'')===String(c?.id||'')):true;
  if(c&&linked&&audit&&leadChanged&&(kind==='create'||c.name==='After Edit'))finding(`${kind}-later-persist-resurrects-failed-save`);
}

if(findings.length){console.error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(';')}`);process.exitCode=1}
else console.log('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_PROBE_SAFE: create+edit success waits for ACK; failed save rolls back client+linked billing+lead+attempt-audit; later persist cannot resurrect');
