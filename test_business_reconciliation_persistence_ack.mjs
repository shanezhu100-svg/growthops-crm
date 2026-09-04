import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);
  if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
let methods;
try{methods=vm.runInNewContext(`({${extract('saveReconciliation')},${extract('voidReconciliation')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: final methods not executable: ${error.message}`)}
for(const name of ['saveReconciliation','voidReconciliation'])if(typeof methods[name]!=='function')throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: ${name} not executable`);

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const fail=message=>{throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};

function parseSave(call){
  if(!call)fail('missing save call');
  const body=JSON.parse(call.body||'{}');
  if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);
  return body.args?.p_state;
}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_RECONCILIATION_SAVE_FAILED'})}}
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}

function makeRuntime({mode,first='fail'}){
  const calls={fetch:[],notify:[]};
  const subject={};
  let confirmAction=null,saveAttempt=0,auditId=0;
  const firstDeferred=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});
    saveAttempt+=1;
    if(saveAttempt===1){
      if(first==='fail')return response(503);
      if(first==='deferred')return firstDeferred.promise;
    }
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

  const matchingActual={providerId:'provider-1',contactId:'contact-1',settlementMonth:'2026-09',currency:'USD',actualRebate:8};
  const option={providerId:'provider-1',contactId:'contact-1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const existingRec={id:'recon-existing',providerId:'provider-1',contactId:'contact-1',providerName:'Agency',contactName:'Alice',settlementMonth:'2026-09',currency:'USD',confirmedSpend:100,actualRebate:8,status:'CONFIRMED'};
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},
    clients:[],backupSnapshots:[],auditLogs:[],financeMonthLocks:{},financeMonthSnapshots:{},
    financeReconciliations:mode==='void'?[existingRec]:[],financeActualRebates:[matchingActual],
    reconciliationSelectedOption:option,
    reconciliationForm:{id:'',settlementMonth:'2026-09',currency:'USD',confirmedSpend:'120',actualRebate:'12',confirmedDate:'2026-09-30',note:'checked'},
    reconciliationSystemSpend:118,reconciliationExpectedRebate:11,showReconciliationModal:true,
    assertMonthUnlocked:()=>true,accountUid:()=> 'recon-new',localDateKey:()=> '2026-09-30',formatMoney:(value,currency)=>`${currency||'USD'}:${value}`,
    askConfirm:(_config,action)=>{confirmAction=action},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action,target};subject.auditLogs.push(row);return row},
    notify:message=>calls.notify.push(String(message)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:[],financeReconciliations:structuredClone(subject.financeReconciliations),financeActualRebates:structuredClone(subject.financeActualRebates),financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,calls,existingRec,matchingActual,getConfirm:()=>confirmAction,resolveFirst:status=>firstDeferred?.resolve(response(status))};
}

// Save failure: no success UI, local accounting/audit is rolled back, rollback itself
// reaches the cloud, and later ordinary persistence cannot resurrect the failed save.
{
  const {subject,calls,matchingActual}=makeRuntime({mode:'save',first:'fail'});
  const task=subject.saveReconciliation();
  ok(task&&typeof task.then==='function','save must expose an ACK promise');
  ok(!calls.notify.some(message=>message.includes('对账已确认')),'save must not announce success before ACK');
  await task;
  eq(subject.financeReconciliations.length,0,'failed save restores pre-attempt reconciliation state');
  eq(subject.financeActualRebates.length,1,'failed save restores prior actual rebate');
  eq(subject.financeActualRebates[0].actualRebate,matchingActual.actualRebate,'failed save restores prior actual rebate value');
  ok(!subject.auditLogs.some(row=>row.action==='代理商返点对账'),'failed save removes attempt audit');
  ok(calls.notify.some(message=>message.includes('云端保存失败')),'failed save must notify durable failure');
  await sleep(240);
  ok(calls.fetch.length>=2,'failed save rollback must itself be persisted');
  const rollback=parseSave(calls.fetch.at(-1));
  eq(rollback.financeReconciliations.length,0,'rollback cloud state excludes failed reconciliation');
  ok(rollback.financeActualRebates.some(r=>r.actualRebate===8),'rollback cloud state restores prior actual rebate');
  ok(!rollback.auditLogs.some(row=>row.action==='代理商返点对账'),'rollback cloud state excludes false success audit');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  eq(later.financeReconciliations.length,0,'later persist cannot resurrect failed reconciliation');
  ok(!later.auditLogs.some(row=>row.action==='代理商返点对账'),'later persist cannot resurrect false reconciliation audit');
}

// Save success: the local tentative row may exist while the network request is in
// flight, but modal closure and success notification are held until the ACK resolves.
{
  const {subject,calls,resolveFirst}=makeRuntime({mode:'save',first:'deferred'});
  const task=subject.saveReconciliation();
  eq(subject.financeReconciliations.length,1,'save tentative reconciliation exists while ACK pending');
  eq(subject.showReconciliationModal,true,'save modal remains open while ACK pending');
  ok(!calls.notify.some(message=>message.includes('对账已确认')),'save success notice held while ACK pending');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful save uses one durable save');
  eq(subject.showReconciliationModal,false,'successful save closes modal after ACK');
  ok(subject.financeReconciliations.some(r=>r.id==='recon-new'&&r.status==='CONFIRMED'),'successful save keeps confirmed reconciliation');
  ok(subject.auditLogs.some(row=>row.action==='代理商返点对账'),'successful save keeps reconciliation audit');
  ok(calls.notify.some(message=>message.includes('对账已确认')),'successful save notifies only after ACK');
}

// Save failure must not overwrite a concurrent replacement for the same accounting
// key or a concurrent unrelated audit created after this attempt entered the barrier.
{
  const {subject,calls,resolveFirst}=makeRuntime({mode:'save',first:'deferred'});
  const task=subject.saveReconciliation();
  const concurrentRec={id:'concurrent',providerId:'provider-1',contactId:'contact-1',settlementMonth:'2026-09',currency:'USD',confirmedSpend:999,actualRebate:99,status:'CONFIRMED'};
  const concurrentActual={providerId:'provider-1',contactId:'contact-1',settlementMonth:'2026-09',currency:'USD',actualRebate:99};
  const concurrentAudit={id:'audit-concurrent',action:'并发审计',target:'keep'};
  subject.financeReconciliations=[concurrentRec];subject.financeActualRebates=[concurrentActual];subject.auditLogs.push(concurrentAudit);
  resolveFirst(503);await task;
  eq(subject.financeReconciliations[0],concurrentRec,'save rollback preserves concurrent same-key reconciliation replacement');
  eq(subject.financeActualRebates[0],concurrentActual,'save rollback preserves concurrent same-key actual rebate');
  ok(subject.auditLogs.includes(concurrentAudit),'save rollback preserves concurrent unrelated audit');
  ok(!subject.auditLogs.some(row=>row.action==='代理商返点对账'),'save rollback removes only attempt audit');
  ok(calls.notify.some(message=>message.includes('云端保存失败')),'concurrent save failure still notifies');
}

// Void failure has the symmetric accounting guarantee: status/rebate/audit return to
// pre-attempt truth and a later save cannot re-persist the failed void.
{
  const {subject,calls,existingRec,getConfirm}=makeRuntime({mode:'void',first:'fail'});
  subject.voidReconciliation({providerName:'Agency',contactName:'Alice',record:existingRec});
  const confirm=getConfirm();ok(typeof confirm==='function','void confirmation missing');
  const task=confirm();
  ok(task&&typeof task.then==='function','void confirmation must expose an ACK promise');
  ok(!calls.notify.some(message=>message.includes('对账已撤销')),'void must not announce success before ACK');
  await task;
  eq(existingRec.status,'CONFIRMED','failed void restores confirmed status');
  eq(subject.financeActualRebates.length,1,'failed void restores removed actual rebate');
  ok(!subject.auditLogs.some(row=>row.action==='撤销代理商返点对账'),'failed void removes attempt audit');
  ok(calls.notify.some(message=>message.includes('云端保存失败')),'failed void must notify durable failure');
  await sleep(240);
  const rollback=parseSave(calls.fetch.at(-1));
  ok(rollback.financeReconciliations.some(r=>r.id==='recon-existing'&&r.status==='CONFIRMED'),'void rollback cloud state restores confirmed record');
  ok(rollback.financeActualRebates.some(r=>r.actualRebate===8),'void rollback cloud state restores actual rebate');
  ok(!rollback.auditLogs.some(row=>row.action==='撤销代理商返点对账'),'void rollback cloud state excludes false audit');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  ok(later.financeReconciliations.some(r=>r.id==='recon-existing'&&r.status==='CONFIRMED'),'later persist cannot resurrect failed void');
}

// Void success is also ACK-gated.
{
  const {subject,calls,existingRec,getConfirm,resolveFirst}=makeRuntime({mode:'void',first:'deferred'});
  subject.voidReconciliation({providerName:'Agency',contactName:'Alice',record:existingRec});
  const confirm=getConfirm();ok(typeof confirm==='function','void success confirmation missing');
  const task=confirm();
  eq(existingRec.status,'VOID','void tentative status exists while ACK pending');
  eq(subject.financeActualRebates.length,0,'void tentative rebate removal exists while ACK pending');
  ok(!calls.notify.some(message=>message.includes('对账已撤销')),'void success notice held while ACK pending');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful void uses one durable save');
  eq(existingRec.status,'VOID','successful void keeps VOID status after ACK');
  eq(subject.financeActualRebates.length,0,'successful void keeps actual rebate removed');
  ok(subject.auditLogs.some(row=>row.action==='撤销代理商返点对账'),'successful void keeps audit');
  ok(calls.notify.some(message=>message.includes('对账已撤销')),'successful void notifies after ACK');
}

// Concurrent same-record changes after a void attempt entered the barrier are not
// overwritten by a failing stale attempt.
{
  const {subject,calls,existingRec,getConfirm,resolveFirst}=makeRuntime({mode:'void',first:'deferred'});
  subject.voidReconciliation({providerName:'Agency',contactName:'Alice',record:existingRec});
  const task=getConfirm()();
  existingRec.status='VOID';existingRec.voidedAt='2099-01-01T00:00:00.000Z';existingRec.voidedBy='Concurrent User';
  const concurrentActual={providerId:'provider-1',contactId:'contact-1',settlementMonth:'2026-09',currency:'USD',actualRebate:77};
  const concurrentAudit={id:'audit-concurrent-void',action:'并发审计',target:'keep'};
  subject.financeActualRebates=[concurrentActual];subject.auditLogs.push(concurrentAudit);
  resolveFirst(503);await task;
  eq(existingRec.voidedAt,'2099-01-01T00:00:00.000Z','void rollback preserves concurrent record mutation');
  eq(existingRec.voidedBy,'Concurrent User','void rollback preserves concurrent actor');
  eq(subject.financeActualRebates[0],concurrentActual,'void rollback preserves concurrent actual rebate');
  ok(subject.auditLogs.includes(concurrentAudit),'void rollback preserves concurrent audit');
  ok(!subject.auditLogs.some(row=>row.action==='撤销代理商返点对账'),'void rollback removes only attempt audit');
  ok(calls.notify.some(message=>message.includes('云端保存失败')),'concurrent void failure still notifies');
}

// If the adapter barrier is absent, both mutation paths fail closed instead of
// degrading back to optimistic/debounced accounting success.
{
  const notifications=[];
  const s=Object.assign({},methods,{
    reconciliationSelectedOption:{providerId:'p',contactId:'c',provider:{name:'Agency'},contact:{name:'Alice'}},
    reconciliationForm:{settlementMonth:'2026-09',currency:'USD',confirmedSpend:'100',actualRebate:'10',confirmedDate:'2026-09-30',note:''},
    reconciliationSystemSpend:100,reconciliationExpectedRebate:10,financeReconciliations:[],financeActualRebates:[],auditLogs:[],showReconciliationModal:true,
    assertMonthUnlocked:()=>true,accountUid:()=> 'recon-missing',localDateKey:()=> '2026-09-30',formatMoney:value=>String(value),persist:()=>true,
    logAudit:(action,target)=>{const row={action,target};s.auditLogs.push(row);return row},notify:message=>notifications.push(String(message)),
  });
  await s.saveReconciliation();
  eq(s.financeReconciliations.length,0,'missing save barrier rolls back reconciliation');
  eq(s.auditLogs.length,0,'missing save barrier rolls back attempt audit');
  eq(s.showReconciliationModal,true,'missing save barrier leaves modal open');
  ok(notifications.some(message=>message.includes('持久化服务不可用')),'missing save barrier notifies fail-closed');
}
{
  const rec={id:'r-missing',status:'CONFIRMED',settlementMonth:'2026-09',providerId:'p',contactId:'c',currency:'USD'};
  let confirmAction=null;const notifications=[];const audits=[];
  const s=Object.assign({},methods,{
    financeReconciliations:[rec],financeActualRebates:[{providerId:'p',contactId:'c',settlementMonth:'2026-09',currency:'USD'}],currentUser:{name:'Finance'},
    assertMonthUnlocked:()=>true,askConfirm:(_config,action)=>{confirmAction=action},persist:()=>true,
    logAudit:(action,target)=>audits.push([action,target]),notify:message=>notifications.push(String(message)),
  });
  s.voidReconciliation({providerName:'Agency',contactName:'Alice',record:rec});
  await confirmAction();
  eq(rec.status,'CONFIRMED','missing void barrier leaves status unchanged');
  eq(s.financeActualRebates.length,1,'missing void barrier leaves actual rebate unchanged');
  eq(audits.length,0,'missing void barrier creates no audit');
  ok(notifications.some(message=>message.includes('持久化服务不可用')),'missing void barrier notifies fail-closed');
}

console.log('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; save+void=success-after-save-ack; failure=accounting-state+attempt-audit-rollback+rollback-persisted; later-persist=failed-operation-not-resurrected; concurrency=same-key/record+unrelated-audit-preserved; missing-barrier=fail-closed');
