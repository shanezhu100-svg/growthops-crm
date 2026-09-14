import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('deleteOpeningProvider')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: final method not executable: ${error.message}`)}
if(typeof methods.deleteOpeningProvider!=='function')throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: deleteOpeningProvider not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
if(!adapter.includes('vm.persistOpeningProviderBarrier=()=>flushSave();'))throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: provider barrier must share flushSave');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_OPENING_PROVIDER_DELETE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const provider=(overrides={})=>({id:'provider-1',name:'Provider A',platforms:'FB+TK',contacts:[],notes:'',...overrides});
const linkedDeal=(overrides={})=>({id:'deal-1',providerId:'provider-1',contactId:'',partnerName:'Provider A',...overrides});

function makeRuntime({first='fail',withBarrier=true,linked=false,canManage=true}={}){
  const calls={fetch:[],notify:[],confirm:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#account-opening'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistOpeningProviderBarrier;
  const target=provider();
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},clients:[],openingProviders:[target],openingDeals:linked?[linkedDeal()]:[],financeCosts:[],auditLogs:[],backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    providerForm:{id:'editor-other',name:'Draft Provider'},showProviderModal:true,
    canManageProviders:()=>canManage,
    askConfirm:(config,action)=>{calls.confirm.push(config);return action()},
    logAudit:(action,targetName)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(targetName)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:[],openingProviders:clone(subject.openingProviders),openingDeals:clone(subject.openingDeals),financeCosts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,target,resolveFirst:status=>gate?.resolve(response(status))};
}

async function waitForFirstFetch(calls){for(let i=0;i<20&&calls.fetch.length===0;i+=1)await sleep(5);eq(calls.fetch.length,1,'delete barrier must issue exactly one pending save before ACK')}
async function persistedRollback(calls){await sleep(240);ok(calls.fetch.length>=2,'delete rollback truth must itself reach serialized save queue');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}

// Confirmed delete is tentative for serialization, while modal close and success
// notification remain held until the shared cloud queue acknowledges it.
{
  const {subject,calls,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.deleteOpeningProvider(target);
  ok(task&&typeof task.then==='function','delete must expose confirmation ACK promise in immediate-confirm harness');
  eq(subject.openingProviders.length,0,'provider is tentatively removed before ACK');
  eq(subject.showProviderModal,true,'provider modal close is held before ACK');
  eq(calls.notify.length,0,'delete success notice is held before ACK');
  eq(subject.auditLogs.filter(a=>a.action==='删除开户商').length,1,'delete attempt audit exists for pending serialization');
  await waitForFirstFetch(calls);
  const pending=parseState(calls.fetch[0]);
  eq((pending.openingProviders||[]).length,0,'pending durable state contains provider deletion');
  eq((pending.auditLogs||[]).filter(a=>a.action==='删除开户商').length,1,'pending durable state contains delete audit');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful provider delete uses exactly one durable save');
  eq(subject.showProviderModal,false,'provider modal closes only after ACK');
  ok(calls.notify.some(m=>m.includes('开户商已删除')),'success notice appears only after ACK');
}

// Failed delete restores the provider and removes only its attempt audit, then persists
// rollback truth so a later save cannot resurrect the failed deletion.
{
  const {subject,calls,target}=makeRuntime({first:'fail'});
  const before=clone(target);
  await subject.deleteOpeningProvider(target);
  eq(subject.openingProviders.length,1,'failed delete restores provider');
  same(subject.openingProviders[0],before,'failed delete restores exact provider prestate');
  ok(!subject.auditLogs.some(a=>a.action==='删除开户商'),'failed delete removes attempt audit');
  eq(subject.showProviderModal,true,'failed delete keeps provider modal state');
  ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed delete explains durable save failure');
  const rollback=await persistedRollback(calls);
  same(rollback.openingProviders?.[0],before,'rollback cloud state restores provider');
  ok(!(rollback.auditLogs||[]).some(a=>a.action==='删除开户商'),'rollback cloud state excludes attempt audit');
  const later=await laterPersist(subject,calls);
  same(later.openingProviders?.[0],before,'later persist keeps restored provider');
  ok(!(later.auditLogs||[]).some(a=>a.action==='删除开户商'),'later persist cannot resurrect failed delete audit');
}

// Rollback is attempt-scoped on the same tentative array: unrelated provider and audit
// writes appended while the ACK is pending remain authoritative.
{
  const {subject,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.deleteOpeningProvider(target);
  const other=provider({id:'provider-other',name:'Other Provider'}),otherAudit={id:'audit-other',action:'并发审计'};
  subject.openingProviders.push(other);subject.auditLogs.push(otherAudit);
  resolveFirst(503);await task;
  eq(subject.openingProviders.length,2,'failed delete restores target without removing unrelated provider');
  ok(subject.openingProviders.includes(other),'unrelated provider survives delete rollback');
  ok(subject.auditLogs.includes(otherAudit),'unrelated audit survives delete rollback');
}

// Same-ID replacement and whole-array replacement are newer authority. A stale failed
// delete must not reinsert the old provider into either concurrent state.
{
  const {subject,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.deleteOpeningProvider(target);
  const replacement=provider({name:'Provider Concurrent'});subject.openingProviders.push(replacement);
  resolveFirst(503);await task;
  eq(subject.openingProviders.length,1,'same-ID replacement prevents stale provider restoration');
  eq(subject.openingProviders[0],replacement,'same-ID replacement remains authoritative');
}
{
  const {subject,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.deleteOpeningProvider(target);
  const replacementArray=[provider({id:'provider-new',name:'Whole Array Authority'})];subject.openingProviders=replacementArray;
  resolveFirst(503);await task;
  eq(subject.openingProviders,replacementArray,'new whole-array provider authority is preserved');
  eq(subject.openingProviders.length,1,'stale target is not inserted into replaced provider array');
}

// A user may start editing another provider while delete ACK is pending. Successful
// completion of the old delete must not close that newer editor.
{
  const {subject,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.deleteOpeningProvider(target);
  const newerForm={id:'provider-new',name:'New Edit'};subject.providerForm=newerForm;subject.showProviderModal=true;
  resolveFirst(200);await task;
  eq(subject.providerForm,newerForm,'newer provider form object remains authoritative after ACK');
  eq(subject.showProviderModal,true,'successful older delete does not close newer provider editor');
}

// Missing durability service fails closed synchronously with zero legacy/network save.
{
  const {subject,calls,target}=makeRuntime({first:'deferred',withBarrier:false});
  const result=subject.deleteOpeningProvider(target);
  eq(result,undefined,'missing barrier returns without successful completion promise');
  eq(calls.fetch.length,0,'missing provider delete barrier issues zero network saves');
  eq(subject.openingProviders.length,1,'missing barrier restores deleted provider');
  ok(!subject.auditLogs.some(a=>a.action==='删除开户商'),'missing barrier removes attempt audit');
  eq(subject.showProviderModal,true,'missing barrier keeps provider modal state');
  ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier explains durability outage');
}

// Existing business guards remain before confirmation/mutation/barrier: linked opening
// records and missing permissions must continue to deny deletion exactly as before.
{
  const {subject,calls,target}=makeRuntime({first:'deferred',linked:true});
  const result=subject.deleteOpeningProvider(target);
  eq(result,undefined,'linked provider delete remains a synchronous denial');
  eq(calls.confirm.length,0,'linked provider is denied before confirmation');
  eq(calls.fetch.length,0,'linked provider denial never reaches durability barrier');
  eq(subject.openingProviders.length,1,'linked provider remains intact');
  ok(calls.notify.some(m=>m.includes('删除受保护')),'linked provider denial explains protected relation');
}
{
  const {subject,calls,target}=makeRuntime({first:'deferred',canManage:false});
  subject.deleteOpeningProvider(target);
  eq(calls.confirm.length,0,'permission denial occurs before confirmation');
  eq(calls.fetch.length,0,'permission denial never reaches durability barrier');
  eq(subject.openingProviders.length,1,'permission denial preserves provider');
  ok(calls.notify.some(m=>m.includes('没有删除开户商的权限')),'permission denial remains truthful');
}

console.log('BUSINESS_OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; delete=linked-guard+single-cloud-ACK-before-success; failure=provider+attempt-audit-rollback+rollback-persisted; concurrency=unrelated+same-id+whole-array+newer-editor-authority-preserved; missing-barrier=fail-closed');
