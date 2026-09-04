import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;
    else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

const storage=new Map();
const localStorage={
  get length(){return storage.size},
  key(index){return [...storage.keys()][index]??null},
  getItem(key){return storage.has(String(key))?storage.get(String(key)):null},
  setItem(key,value){storage.set(String(key),String(value))},
  removeItem(key){storage.delete(String(key))},
  clear(){storage.clear()},
};

let deleteClient;
try{deleteClient=vm.runInNewContext(`({${extractMethod('deleteClient')}}).deleteClient`,{localStorage,Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: final deleteClient not executable: ${error.message}`)}
if(typeof deleteClient!=='function')throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: deleteClient not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_CLIENT_DELETE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const hasId=(rows,id)=>Array.isArray(rows)&&rows.some(row=>String(row?.id??'')===String(id));
const hasClientRef=(rows,id)=>Array.isArray(rows)&&rows.some(row=>String(row?.clientId??'')===String(id));

function makeRuntime({first='fail',withBarrier=true}={}){
  storage.clear();
  localStorage.setItem('growthOpsSop-1-FB:acct-2026-09-01','sop-before');
  localStorage.setItem('sop-1-2026-09-01','legacy-before');
  localStorage.setItem('growthOpsSop-2-FB:other-2026-09-01','survivor-sop');
  localStorage.setItem('unrelated-key','keep');
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#clients'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistClientDeleteBarrier;
  const client={id:1,name:'Deleted Client',archived:true,notes:'client-before',fbAccounts:[{adDataRecords:[{}]}],tkAccounts:[],adCampaigns:[{}]};
  const survivor={id:2,name:'Survivor',archived:false};
  const linkedLead={id:'lead-1',stage:'WON',convertedClientId:1,convertedAt:'2026-08-01T00:00:00.000Z',notes:'lead-before'};
  const unrelatedLead={id:'lead-2',stage:'WON',convertedClientId:2,convertedAt:'2026-08-02T00:00:00.000Z'};
  Object.assign(subject,{
    deleteClient,currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},
    clients:[client,survivor],leads:[linkedLead,unrelatedLead],openingProviders:[],
    openingDeals:[{id:'o1',clientId:1,name:'opening-before'},{id:'o2',clientId:2}],
    financeReceivables:[{id:'r1',clientId:1,payments:[]},{id:'r2',clientId:2,payments:[]}],
    financeCosts:[{id:'c1',clientId:1},{id:'c2',clientId:2}],
    standaloneAlerts:[{id:'a1',clientId:1},{id:'a2',clientId:2}],dismissedAlerts:[{id:'d1',clientId:1},{id:'d2',clientId:2}],
    mediaTools:[{id:'t1',name:'tool-before',bindings:[{clientId:1,accountKey:'ALL',note:'binding-before'},{clientId:2,accountKey:'ALL'}]}],
    auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    selectedClientId:1,selectedAssetsClientId:1,selectedSopClientId:1,selectedAnalyticsClientId:1,selectedAdsClientId:1,
    clientRelationSummary:()=>({adRecords:1,campaigns:1,openings:1,receivables:1,costs:1,tools:1,total:6}),
    askConfirm:(config,action)=>{subject.__confirm={config,action}},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},
    collectBackupPayload:()=>({
      clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:clone(subject.openingProviders),openingDeals:clone(subject.openingDeals),
      financeCosts:clone(subject.financeCosts),financeReceivables:clone(subject.financeReceivables),standaloneAlerts:clone(subject.standaloneAlerts),dismissedAlerts:clone(subject.dismissedAlerts),mediaTools:clone(subject.mediaTools),
      auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    }),
  });
  return {subject,client,linkedLead,calls,before:{client:clone(client),lead:clone(linkedLead),opening:clone(subject.openingDeals[0]),receivable:clone(subject.financeReceivables[0]),cost:clone(subject.financeCosts[0]),alert:clone(subject.standaloneAlerts[0]),dismissed:clone(subject.dismissedAlerts[0]),tool:clone(subject.mediaTools[0])},resolveFirst:status=>gate?.resolve(response(status))};
}
function confirm(subject){if(typeof subject.__confirm?.action!=='function')fail('confirmation callback missing');return subject.__confirm.action()}
async function waitFirstSave(calls){for(let i=0;i<30&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending durable save before ACK')}
async function waitRollback(calls){await sleep(240);ok(calls.fetch.length>=2,'rollback truth must reach serialized save queue');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}
function assertCascadeRestored(subject,before,label){
  same(subject.clients.find(row=>String(row.id)==='1'),before.client,`${label} restores client`);
  same(subject.openingDeals.find(row=>row.id==='o1'),before.opening,`${label} restores opening deal`);
  same(subject.financeReceivables.find(row=>row.id==='r1'),before.receivable,`${label} restores receivable`);
  same(subject.financeCosts.find(row=>row.id==='c1'),before.cost,`${label} restores cost`);
  same(subject.standaloneAlerts.find(row=>row.id==='a1'),before.alert,`${label} restores standalone alert`);
  same(subject.dismissedAlerts.find(row=>row.id==='d1'),before.dismissed,`${label} restores dismissed alert`);
  same(subject.leads.find(row=>row.id==='lead-1'),before.lead,`${label} restores lead link fields`);
  same(subject.mediaTools.find(row=>row.id==='t1'),before.tool,`${label} restores tool binding`);
}
function assertCloudCascadeRestored(state,before,label){
  same((state.clients||[]).find(row=>String(row.id)==='1'),before.client,`${label} cloud restores client`);
  same((state.openingDeals||[]).find(row=>row.id==='o1'),before.opening,`${label} cloud restores opening deal`);
  same((state.financeReceivables||[]).find(row=>row.id==='r1'),before.receivable,`${label} cloud restores receivable`);
  same((state.financeCosts||[]).find(row=>row.id==='c1'),before.cost,`${label} cloud restores cost`);
  same((state.standaloneAlerts||[]).find(row=>row.id==='a1'),before.alert,`${label} cloud restores standalone alert`);
  same((state.dismissedAlerts||[]).find(row=>row.id==='d1'),before.dismissed,`${label} cloud restores dismissed alert`);
  same((state.leads||[]).find(row=>row.id==='lead-1'),before.lead,`${label} cloud restores lead`);
  same((state.mediaTools||[]).find(row=>row.id==='t1'),before.tool,`${label} cloud restores tool`);
}

// Success is not user-visible until the exact full cascade reaches one cloud ACK.
{
  const {subject,client,calls,resolveFirst}=makeRuntime({first:'deferred'});
  subject.deleteClient(client);const task=confirm(subject);
  ok(task&&typeof task.then==='function','confirmation callback exposes ACK promise');
  await waitFirstSave(calls);
  eq(calls.notify.filter(m=>m.includes('已删除')).length,0,'success notice held before ACK');
  const pending=parseState(calls.fetch[0]);
  ok(!hasId(pending.clients,1),'tentative cloud state deletes client');
  ok(!hasClientRef(pending.openingDeals,1),'tentative cloud state deletes client opening deals');
  ok(!hasClientRef(pending.financeReceivables,1),'tentative cloud state deletes client receivables');
  ok(!hasClientRef(pending.financeCosts,1),'tentative cloud state deletes client costs');
  eq((pending.leads||[]).find(row=>row.id==='lead-1')?.convertedClientId,null,'tentative cloud state clears lead pointer');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful permanent delete uses one durable save');
  eq(calls.notify.filter(m=>m.includes('已删除')).length,1,'success notice emitted after ACK');
}

// Failed save restores the entire attempt-owned cascade, SOP progress, selections and
// attempt audit, persists rollback truth, and later ordinary persist cannot resurrect it.
{
  const {subject,client,calls,before}=makeRuntime({first:'fail'});
  subject.deleteClient(client);await Promise.resolve(confirm(subject));
  assertCascadeRestored(subject,before,'503 rollback');
  eq(subject.auditLogs.length,0,'503 rollback removes only delete attempt audit');
  for(const key of ['selectedClientId','selectedAssetsClientId','selectedSopClientId','selectedAnalyticsClientId','selectedAdsClientId'])eq(String(subject[key]),'1',`503 rollback restores ${key}`);
  eq(localStorage.getItem('growthOpsSop-1-FB:acct-2026-09-01'),'sop-before','503 rollback restores modern SOP progress');
  eq(localStorage.getItem('sop-1-2026-09-01'),'legacy-before','503 rollback restores legacy SOP progress');
  eq(localStorage.getItem('growthOpsSop-2-FB:other-2026-09-01'),'survivor-sop','503 rollback preserves unrelated SOP progress');
  ok(calls.notify.some(m=>m.includes('云端保存失败')),'503 rollback explains durable failure');
  const rollback=await waitRollback(calls);
  assertCloudCascadeRestored(rollback,before,'503 rollback save');
  eq((rollback.auditLogs||[]).length,0,'rollback cloud excludes failed delete audit');
  const later=await laterPersist(subject,calls);
  assertCloudCascadeRestored(later,before,'later persist');
  eq((later.auditLogs||[]).length,0,'later persist cannot resurrect failed delete audit');
}

// Concurrent state created while ACK is pending remains newer authority. Rollback may
// restore only values still equal to this delete attempt's own after-state.
{
  const {subject,client,linkedLead,calls,resolveFirst}=makeRuntime({first:'deferred'});
  subject.deleteClient(client);const task=confirm(subject);await waitFirstSave(calls);
  const clientReplacement={id:1,name:'Concurrent Client',archived:true,notes:'replacement'};
  const openingReplacement={id:'o1',clientId:1,name:'concurrent-opening'};
  const toolReplacement={id:'t1',name:'concurrent-tool',bindings:[{clientId:1,accountKey:'NEW'}]};
  const unrelatedOpening={id:'o-new',clientId:2,name:'unrelated-new'};
  const unrelatedAudit={id:'audit-concurrent',action:'并发审计'};
  subject.clients.push(clientReplacement);
  subject.openingDeals.push(openingReplacement,unrelatedOpening);
  subject.mediaTools.splice(0,1,toolReplacement);
  linkedLead.convertedClientId='concurrent-client';
  linkedLead.notes='lead-concurrent';
  subject.selectedClientId='selection-concurrent';
  localStorage.setItem('growthOpsSop-1-FB:acct-2026-09-01','sop-concurrent');
  subject.auditLogs.push(unrelatedAudit);
  resolveFirst(503);await task;
  eq(subject.clients.find(row=>String(row.id)==='1'),clientReplacement,'same-ID client replacement preserved');
  eq(subject.openingDeals.find(row=>row.id==='o1'),openingReplacement,'same-ID related-row replacement preserved');
  ok(subject.openingDeals.includes(unrelatedOpening),'unrelated concurrent row preserved');
  eq(subject.mediaTools.find(row=>row.id==='t1'),toolReplacement,'same-ID tool replacement preserved');
  eq(linkedLead.convertedClientId,'concurrent-client','newer lead pointer preserved');
  eq(linkedLead.notes,'lead-concurrent','unrelated concurrent lead field preserved');
  eq(subject.selectedClientId,'selection-concurrent','newer selection preserved');
  eq(localStorage.getItem('growthOpsSop-1-FB:acct-2026-09-01'),'sop-concurrent','recreated SOP value preserved');
  ok(subject.auditLogs.includes(unrelatedAudit),'unrelated concurrent audit preserved');
  ok(!subject.auditLogs.some(row=>row!==unrelatedAudit&&String(row.action||'').includes('删除')),'failed attempt audit removed without touching concurrent audit');
}

// Field-level lead rollback restores only unchanged attempt-owned fields.
{
  const {subject,client,linkedLead,resolveFirst}=makeRuntime({first:'deferred'});
  subject.deleteClient(client);const task=confirm(subject);
  linkedLead.convertedAt='concurrent-time';
  resolveFirst(503);await task;
  eq(linkedLead.convertedClientId,1,'unchanged attempted lead pointer rolls back');
  eq(linkedLead.convertedAt,'concurrent-time','newer lead timestamp remains authoritative');
}

// Missing durability service fails closed: complete local rollback, no save request.
{
  const {subject,client,calls,before}=makeRuntime({first:'deferred',withBarrier:false});
  subject.deleteClient(client);const result=confirm(subject);
  eq(result,undefined,'missing barrier returns without success promise');
  eq(calls.fetch.length,0,'missing barrier issues zero network saves');
  assertCascadeRestored(subject,before,'missing barrier');
  eq(subject.auditLogs.length,0,'missing barrier removes attempt audit');
  for(const key of ['selectedClientId','selectedAssetsClientId','selectedSopClientId','selectedAnalyticsClientId','selectedAdsClientId'])eq(String(subject[key]),'1',`missing barrier restores ${key}`);
  eq(localStorage.getItem('growthOpsSop-1-FB:acct-2026-09-01'),'sop-before','missing barrier restores SOP progress');
  ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier explains unavailable service');
}

console.log('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; permanent-delete=success-after-save-ack; failure=complete-cascade+SOP+attempt-audit-rollback+rollback-persisted; later-persist=failed-delete-not-resurrected; concurrency=same-id+lead-field+tool+selection+SOP-replacement-preserved; missing-barrier=fail-closed');
