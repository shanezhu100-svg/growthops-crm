import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extract(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

let methods;
try{methods=vm.runInNewContext(`({${['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment','deleteReceivablePayment'].map(extract).join(',')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: final methods not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const fail=message=>{throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_PAYMENT_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state}

function makeRuntime({kind,first='fail',withBarrier=true}){
  const calls={fetch:[],notify:[]};
  const subject={};
  let saveAttempt=0,confirmAction=null,auditId=0,uid=0;
  const gate=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistReceivablePaymentBarrier;

  const row=kind==='save'
    ?{id:'recv-save',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',incomeType:'SERVICE_FEE',payments:[],paidAmount:0}
    :{id:'recv-delete',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',incomeType:'SERVICE_FEE',payments:[{id:'pay-delete',date:'2026-09-04',amount:40,method:'银行转账',account:'acct',note:''},{id:'pay-keep',date:'2026-09-03',amount:10,method:'银行转账',account:'acct',note:''}],paidAmount:50};
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},clients:[{id:'c1',name:'Alpha'}],
    financeReceivables:[row],financeCosts:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],backupSnapshots:[],auditLogs:[],
    paymentTargetReceivable:row,paymentForm:{date:'2026-09-04',amount:'40',method:'银行转账',account:'acct',note:'received'},receivableForm:null,showPaymentModal:true,
    assertMonthUnlocked:()=>true,isMonthLocked:()=>false,localDateKey:()=> '2026-09-04',accountUid:prefix=>`${prefix}-${++uid}`,
    financeReceivableClientName:()=> 'Alpha',financeIncomeTypeText:()=> '投放服务费',formatMoney:(v,c)=>`${c||'USD'}:${Number(v)}`,normalizeReceivable:r=>({...r}),
    askConfirm:(_config,action)=>{confirmAction=action},
    logAudit:(action,target)=>{const audit={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(audit);return audit},
    notify:message=>calls.notify.push(String(message)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),financeReceivables:structuredClone(subject.financeReceivables),financeCosts:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,row,calls,getConfirm:()=>confirmAction,resolveFirst:status=>gate?.resolve(response(status))};
}

// Create failure: tentative payment/audit must roll back, rollback truth must itself
// reach the serialized cloud save queue, and a later ordinary persist must stay clean.
{
  const {subject,row,calls}=makeRuntime({kind:'save',first:'fail'});
  const task=subject.saveReceivablePayment();
  ok(task&&typeof task.then==='function','save must expose ACK promise');
  ok(!calls.notify.some(m=>m.includes('回款流水已保存')),'save success must wait for ACK');
  await task;
  eq(row.payments.length,0,'failed save removes tentative payment');eq(subject.financeReceivablePaid(row),0,'failed save restores paid total');
  ok(!subject.auditLogs.some(a=>String(a.action).includes('回款')),'failed save removes attempt audit');ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed save notifies durable failure');
  await sleep(240);ok(calls.fetch.length>=2,'save rollback must itself persist');
  const rollback=parseState(calls.fetch.at(-1)),saved=rollback.financeReceivables.find(r=>r.id===row.id);
  eq(saved.payments.length,0,'save rollback cloud state excludes failed payment');ok(!rollback.auditLogs.some(a=>String(a.action).includes('回款')),'save rollback cloud state excludes false audit');
  subject.persist();await sleep(240);const later=parseState(calls.fetch.at(-1));eq(later.financeReceivables.find(r=>r.id===row.id).payments.length,0,'later persist cannot resurrect failed payment');
}

// Create success: payment can be tentative in local memory, but UI success is held
// until the network acknowledgement resolves.
{
  const {subject,row,calls,resolveFirst}=makeRuntime({kind:'save',first:'deferred'});
  const task=subject.saveReceivablePayment();eq(row.payments.length,1,'save tentative payment exists while ACK pending');eq(subject.showPaymentModal,true,'payment modal stays open while ACK pending');ok(!calls.notify.some(m=>m.includes('回款流水已保存')),'save notice held while ACK pending');
  resolveFirst(200);await task;eq(calls.fetch.length,1,'successful save uses one durable save');eq(row.payments.length,1,'successful save keeps payment');eq(subject.showPaymentModal,false,'successful save closes modal after ACK');ok(calls.notify.some(m=>m.includes('回款流水已保存')),'successful save notifies after ACK');
}

// Create failure with concurrent state: remove only the failed attempt payment, while a
// concurrently added real payment and unrelated audit survive with a recomputed total.
{
  const {subject,row,calls,resolveFirst}=makeRuntime({kind:'save',first:'deferred'});
  const task=subject.saveReceivablePayment();const attempt=row.payments[0];
  const concurrent={id:'pay-concurrent',date:'2026-09-04',amount:15};const concurrentAudit={id:'audit-concurrent',action:'并发审计',target:'keep'};row.payments.push(concurrent);row.paidAmount=55;subject.auditLogs.push(concurrentAudit);
  resolveFirst(503);await task;
  ok(!row.payments.includes(attempt),'save rollback removes failed attempt payment');ok(row.payments.includes(concurrent),'save rollback preserves concurrent payment');eq(subject.financeReceivablePaid(row),15,'save rollback recomputes concurrent paid total');ok(subject.auditLogs.includes(concurrentAudit),'save rollback preserves unrelated audit');ok(calls.notify.some(m=>m.includes('云端保存失败')),'concurrent save failure notifies');
}

// Delete failure: deleted payment/paid total/audit must return to pre-attempt truth and
// later persistence cannot resurrect the failed deletion.
{
  const {subject,row,calls,getConfirm}=makeRuntime({kind:'delete',first:'fail'});const removed=row.payments[0];
  subject.deleteReceivablePayment(row,removed);const confirm=getConfirm();ok(typeof confirm==='function','delete confirmation missing');const task=confirm();ok(task&&typeof task.then==='function','delete callback must expose ACK promise');ok(!calls.notify.some(m=>m.includes('回款流水已删除')),'delete success must wait for ACK');await task;
  ok(row.payments.some(p=>p.id==='pay-delete'),'failed delete restores removed payment');eq(subject.financeReceivablePaid(row),50,'failed delete restores paid total');ok(!subject.auditLogs.some(a=>a.action==='删除回款流水'),'failed delete removes attempt audit');
  await sleep(240);const rollback=parseState(calls.fetch.at(-1)),saved=rollback.financeReceivables.find(r=>r.id===row.id);ok(saved.payments.some(p=>p.id==='pay-delete'),'delete rollback cloud state restores payment');ok(!rollback.auditLogs.some(a=>a.action==='删除回款流水'),'delete rollback excludes false audit');
  subject.persist();await sleep(240);const later=parseState(calls.fetch.at(-1));ok(later.financeReceivables.find(r=>r.id===row.id).payments.some(p=>p.id==='pay-delete'),'later persist cannot resurrect failed deletion');
}

// Delete success is ACK-gated.
{
  const {subject,row,calls,getConfirm,resolveFirst}=makeRuntime({kind:'delete',first:'deferred'});const removed=row.payments[0];subject.deleteReceivablePayment(row,removed);const task=getConfirm()();
  ok(!row.payments.some(p=>p.id==='pay-delete'),'delete tentative removal exists while ACK pending');ok(!calls.notify.some(m=>m.includes('回款流水已删除')),'delete notice held while ACK pending');resolveFirst(200);await task;eq(calls.fetch.length,1,'successful delete uses one durable save');ok(!row.payments.some(p=>p.id==='pay-delete'),'successful delete remains removed');eq(subject.financeReceivablePaid(row),10,'successful delete keeps recalculated paid total');ok(calls.notify.some(m=>m.includes('回款流水已删除')),'successful delete notifies after ACK');
}

// A failed delete merges its rollback with concurrent unrelated ledger changes. The
// original deleted payment is restored at its prior slot without removing a new payment.
{
  const {subject,row,calls,getConfirm,resolveFirst}=makeRuntime({kind:'delete',first:'deferred'});const removed=row.payments[0];subject.deleteReceivablePayment(row,removed);const task=getConfirm()();
  const concurrent={id:'pay-concurrent-delete',date:'2026-09-04',amount:7};const concurrentAudit={id:'audit-concurrent-delete',action:'并发审计',target:'keep'};row.payments.push(concurrent);row.paidAmount=17;subject.auditLogs.push(concurrentAudit);resolveFirst(503);await task;
  ok(row.payments.some(p=>p===removed),'delete rollback restores failed-deletion payment');ok(row.payments.includes(concurrent),'delete rollback preserves concurrent payment');eq(subject.financeReceivablePaid(row),57,'delete rollback recomputes combined paid total');ok(subject.auditLogs.includes(concurrentAudit),'delete rollback preserves concurrent audit');ok(!subject.auditLogs.some(a=>a.action==='删除回款流水'),'delete rollback removes attempt audit');ok(calls.notify.some(m=>m.includes('云端保存失败')),'concurrent delete failure notifies');
}

// Same-ID concurrent replacement is authoritative: a stale rollback must not insert
// another copy of the old removed payment over the replacement.
{
  const {subject,row,getConfirm,resolveFirst}=makeRuntime({kind:'delete',first:'deferred'});const removed=row.payments[0];subject.deleteReceivablePayment(row,removed);const task=getConfirm()();const replacement={id:'pay-delete',date:'2026-09-04',amount:99,note:'concurrent replacement'};row.payments.push(replacement);row.paidAmount=109;resolveFirst(503);await task;
  eq(row.payments.filter(p=>p.id==='pay-delete').length,1,'same-ID concurrent replacement remains unique');eq(row.payments.find(p=>p.id==='pay-delete'),replacement,'same-ID concurrent replacement is not overwritten');
}

// Missing adapter helper fails closed instead of silently reverting to debounced
// optimistic success.
{
  const {subject,row,calls}=makeRuntime({kind:'save',withBarrier:false});await subject.saveReceivablePayment();eq(row.payments.length,0,'missing save barrier rolls back payment');eq(subject.financeReceivablePaid(row),0,'missing save barrier restores paid total');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing save barrier notifies fail-closed');
}
{
  const {subject,row,calls,getConfirm}=makeRuntime({kind:'delete',withBarrier:false});const removed=row.payments[0];subject.deleteReceivablePayment(row,removed);await getConfirm()();ok(row.payments.includes(removed),'missing delete barrier leaves payment untouched');eq(subject.financeReceivablePaid(row),50,'missing delete barrier leaves paid total untouched');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing delete barrier notifies fail-closed');
}

console.log('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; save+delete=success-after-save-ack; failure=payment+paid-total+attempt-audit-rollback+rollback-persisted; later-persist=failed-operation-not-resurrected; concurrency=unrelated-payment+audit-preserved+same-id-replacement-authoritative; missing-barrier=fail-closed');
