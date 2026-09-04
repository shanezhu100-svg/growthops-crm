import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${['archiveClient','restoreClient','deleteLead'].map(extractMethod).join(',')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: final methods not executable: ${error.message}`)}
for(const name of ['archiveClient','restoreClient','deleteLead'])if(typeof methods[name]!=='function')throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: ${name} not executable`);

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LIFECYCLE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

const activeClient=(overrides={})=>({id:'client-1',name:'Client One',archived:false,status:'ACTIVE',archivedAt:'',notes:'client-before',...overrides});
const archivedClient=(overrides={})=>({id:'client-1',name:'Client One',archived:true,status:'PAUSED',archivedAt:'2026-08-01T00:00:00.000Z',notes:'client-before',...overrides});
const lead=(overrides={})=>({id:'lead-1',company:'Lead One',stage:'NEW',notes:'lead-before',...overrides});
const actionFor=kind=>kind==='archive'?'归档客户':kind==='restore'?'恢复归档客户':'删除潜在客户';
const successText=kind=>kind==='archive'?'已归档':kind==='restore'?'已恢复':'已删除';

function makeRuntime({kind,first='fail',withBarrier=true}){
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#clients'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistClientLifecycleBarrier;
  const client=kind==='restore'?archivedClient():activeClient();
  const sourceLead=lead();
  Object.assign(subject,methods,{
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},clients:[clone(client)],leads:[clone(sourceLead)],openingProviders:[],openingDeals:[],financeCosts:[],auditLogs:[],backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    canArchiveClients:()=>true,
    askConfirm:(config,action)=>{subject.__confirm={config,action}},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeCosts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  const target=kind==='lead'?subject.leads[0]:subject.clients[0];
  return {subject,target,calls,beforeClient:clone(client),beforeLead:clone(sourceLead),resolveFirst:status=>gate?.resolve(response(status))};
}
function invoke(kind,subject,target){return kind==='archive'?subject.archiveClient(target):kind==='restore'?subject.restoreClient(target):subject.deleteLead(target)}
function confirm(subject){if(typeof subject.__confirm?.action!=='function')fail('confirmation callback missing');return subject.__confirm.action()}
async function waitFirstSave(calls){for(let i=0;i<20&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending durable save before ACK')}
async function waitRollback(calls){await sleep(240);ok(calls.fetch.length>=2,'rollback truth must reach serialized save queue');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}

// User-visible completion is delayed until the exact tentative state reaches cloud ACK.
for(const kind of ['archive','restore','lead']){
  const {subject,target,calls,resolveFirst}=makeRuntime({kind,first:'deferred'});
  invoke(kind,subject,target);
  const task=confirm(subject);
  ok(task&&typeof task.then==='function',`${kind} confirmation callback exposes ACK promise`);
  await waitFirstSave(calls);
  eq(calls.notify.filter(m=>m.includes(successText(kind))).length,0,`${kind} success notice held before ACK`);
  const pending=parseState(calls.fetch[0]);
  if(kind==='archive')eq(pending.clients?.[0]?.archived,true,'archive tentative state serialized');
  else if(kind==='restore')eq(pending.clients?.[0]?.archived,false,'restore tentative state serialized');
  else eq((pending.leads||[]).some(row=>String(row.id)==='lead-1'),false,'lead delete tentative state serialized');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,`${kind} success uses one durable save`);
  eq(calls.notify.filter(m=>m.includes(successText(kind))).length,1,`${kind} success notice emitted after ACK`);
}

// Failed saves restore local truth, remove only attempt audit, persist the rollback and
// cannot be resurrected by a later ordinary persist.
for(const kind of ['archive','restore','lead']){
  const {subject,target,calls,beforeClient,beforeLead}=makeRuntime({kind,first:'fail'});
  invoke(kind,subject,target);await confirm(subject);
  ok(!subject.auditLogs.some(a=>a.action===actionFor(kind)),`${kind} failed save removes attempt audit`);
  if(kind==='lead')same(subject.leads[0],beforeLead,'lead failed save restores deleted lead');
  else same(subject.clients[0],beforeClient,`${kind} failed save restores lifecycle prestate`);
  ok(calls.notify.some(m=>m.includes('云端保存失败')),`${kind} failed save explains durable failure`);
  const rollback=await waitRollback(calls);
  ok(!(rollback.auditLogs||[]).some(a=>a.action===actionFor(kind)),`${kind} rollback cloud excludes attempt audit`);
  if(kind==='lead')same(rollback.leads?.[0],beforeLead,'lead rollback cloud restores lead');
  else same(rollback.clients?.[0],beforeClient,`${kind} rollback cloud restores client`);
  const later=await laterPersist(subject,calls);
  ok(!(later.auditLogs||[]).some(a=>a.action===actionFor(kind)),`${kind} later persist cannot resurrect audit`);
  if(kind==='lead')same(later.leads?.[0],beforeLead,'lead later persist cannot resurrect failed deletion');
  else same(later.clients?.[0],beforeClient,`${kind} later persist cannot resurrect failed lifecycle change`);
}

// Unrelated state and audits appended while ACK is pending remain authoritative.
for(const kind of ['archive','restore','lead']){
  const {subject,target,resolveFirst}=makeRuntime({kind,first:'deferred'});
  invoke(kind,subject,target);const task=confirm(subject);
  const otherClient=activeClient({id:'client-other',name:'Other Client'}),otherLead=lead({id:'lead-other',company:'Other Lead'}),otherAudit={id:'audit-other',action:'并发审计'};
  subject.clients.push(otherClient);subject.leads.push(otherLead);subject.auditLogs.push(otherAudit);
  resolveFirst(503);await task;
  ok(subject.clients.includes(otherClient),`${kind} rollback preserves unrelated client`);
  ok(subject.leads.includes(otherLead),`${kind} rollback preserves unrelated lead`);
  ok(subject.auditLogs.includes(otherAudit),`${kind} rollback preserves unrelated audit`);
}

// Same-ID replacement objects are newer truth and must not be overwritten by rollback.
for(const kind of ['archive','restore']){
  const {subject,target,resolveFirst}=makeRuntime({kind,first:'deferred'});
  invoke(kind,subject,target);const task=confirm(subject);
  const replacement=activeClient({name:'Concurrent Client',archived:kind==='archive',status:kind==='archive'?'PAUSED':'ACTIVE',archivedAt:kind==='archive'?'concurrent':''});
  subject.clients.splice(0,1,replacement);
  resolveFirst(503);await task;
  eq(subject.clients[0],replacement,`${kind} same-ID client replacement remains authoritative`);
}
{
  const {subject,target,resolveFirst}=makeRuntime({kind:'lead',first:'deferred'});
  invoke('lead',subject,target);const task=confirm(subject);
  const replacement=lead({company:'Concurrent Lead'});subject.leads.push(replacement);
  resolveFirst(503);await task;
  eq(subject.leads.find(row=>String(row.id)==='lead-1'),replacement,'lead same-ID replacement remains authoritative');
}

// Same client object gets field-level rollback: unrelated concurrent fields survive,
// while attempt-owned lifecycle fields restore unless those fields have newer values.
{
  const {subject,target,resolveFirst}=makeRuntime({kind:'archive',first:'deferred'});
  invoke('archive',subject,target);const task=confirm(subject);const row=subject.clients[0];row.notes='concurrent-note';
  resolveFirst(503);await task;
  eq(row.archived,false,'archive attempt field rolls back');eq(row.status,'ACTIVE','archive status rolls back');eq(row.archivedAt,'','archive timestamp rolls back');eq(row.notes,'concurrent-note','archive unrelated field survives');
}
{
  const {subject,target,resolveFirst}=makeRuntime({kind:'archive',first:'deferred'});
  invoke('archive',subject,target);const task=confirm(subject);const row=subject.clients[0];row.status='SUSPENDED';
  resolveFirst(503);await task;
  eq(row.archived,false,'archive unchanged attempt flag rolls back');eq(row.status,'SUSPENDED','newer lifecycle field remains authoritative');eq(row.archivedAt,'','archive timestamp rolls back');
}

// Missing durability service fails closed without issuing network traffic.
for(const kind of ['archive','restore','lead']){
  const {subject,target,calls,beforeClient,beforeLead}=makeRuntime({kind,first:'deferred',withBarrier:false});
  invoke(kind,subject,target);const result=confirm(subject);
  eq(result,undefined,`${kind} missing barrier returns without success promise`);
  eq(calls.fetch.length,0,`${kind} missing barrier issues zero saves`);
  ok(!subject.auditLogs.some(a=>a.action===actionFor(kind)),`${kind} missing barrier removes attempt audit`);
  ok(calls.notify.some(m=>m.includes('持久化服务不可用')),`${kind} missing barrier explains unavailable service`);
  if(kind==='lead')same(subject.leads[0],beforeLead,'lead missing barrier restores source');
  else same(subject.clients[0],beforeClient,`${kind} missing barrier restores source`);
}

console.log('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; archive+restore+lead-delete=success-after-save-ack; failure=lifecycle-or-lead+attempt-audit-rollback+rollback-persisted; later-persist=failed-operation-not-resurrected; concurrency=unrelated-state+same-id-replacement+client-field-level-preserved; missing-barrier=fail-closed');
