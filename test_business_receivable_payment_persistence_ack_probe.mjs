import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extract(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

let methods;
try{methods=vm.runInNewContext(`({${['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment','deleteReceivablePayment'].map(extract).join(',')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: final methods not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_PAYMENT_SAVE_FAILED'})}}
function parseState(call){
  const body=JSON.parse(call?.body||'{}');
  if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);
  return body.args?.p_state;
}

function makeRuntime(kind){
  const calls={fetch:[],notify:[]};
  const subject={};
  let saveAttempt=0,confirmAction=null,auditId=0,uid=0;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});
    saveAttempt+=1;
    return response(saveAttempt===1?503:200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

  const row=kind==='save'
    ?{id:'receivable-save',clientId:'client-1',amount:100,currency:'USD',settlementMonth:'2026-09',dueDate:'2026-09-30',incomeType:'SERVICE_FEE',payments:[],paidAmount:0}
    :{id:'receivable-delete',clientId:'client-1',amount:100,currency:'USD',settlementMonth:'2026-09',dueDate:'2026-09-30',incomeType:'SERVICE_FEE',payments:[{id:'pay-delete',date:'2026-09-04',amount:40,method:'银行转账',account:'acct',note:''},{id:'pay-keep',date:'2026-09-03',amount:10,method:'银行转账',account:'acct',note:''}],paidAmount:50};
  Object.assign(subject,methods,{
    currentUser:{id:'finance-user',name:'Finance User',role:'FINANCE',enabled:true},
    clients:[{id:'client-1',name:'Alpha'}],financeReceivables:[row],financeCosts:[],backupSnapshots:[],auditLogs:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    paymentTargetReceivable:row,paymentForm:{date:'2026-09-04',amount:'40',method:'银行转账',account:'acct',note:'received'},receivableForm:null,showPaymentModal:true,
    assertMonthUnlocked:()=>true,isMonthLocked:()=>false,localDateKey:()=> '2026-09-04',accountUid:prefix=>`${prefix}-${++uid}`,
    financeReceivableClientName:()=> 'Alpha',financeIncomeTypeText:()=> '投放服务费',formatMoney:(value,currency)=>`${currency||'USD'}:${Number(value)}`,normalizeReceivable:r=>({...r}),receivableLinkedCost:()=>null,
    askConfirm:(_config,action)=>{confirmAction=action},
    logAudit:(action,target)=>{const audit={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(audit);return audit},
    notify:message=>calls.notify.push(String(message)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),financeReceivables:structuredClone(subject.financeReceivables),financeCosts:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,row,calls,getConfirm:()=>confirmAction};
}

const findings=[];
const finding=(id,condition,detail)=>{if(condition)findings.push(`${id}: ${detail}`)};

// SAVE: the current shipped path mutates the real payment ledger, schedules the
// debounced cloud save, writes its success audit/notice, and returns before the cloud
// has acknowledged the accounting state. A failed first save therefore remains live
// and can be included by a later otherwise-unrelated persist.
{
  const {subject,row,calls}=makeRuntime('save');
  subject.saveReceivablePayment();
  finding('save-success-before-ack',row.payments.length===1&&calls.notify.some(message=>message.includes('回款流水已保存'))&&calls.fetch.length===0,'payment and success notice exist before any crm_save_state acknowledgement');
  await sleep(240);
  finding('save-503-local-state',calls.fetch.length>=1&&row.payments.length===1&&subject.financeReceivablePaid(row)===40&&subject.auditLogs.length>0,'503 leaves failed payment, paid total, and success audit in live memory');
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const saved=later?.financeReceivables?.find(r=>r.id===row.id);
  finding('save-later-persist-resurrects',calls.fetch.length>=2&&saved?.payments?.some(p=>Number(p.amount)===40)&&later?.auditLogs?.some(a=>String(a.action).includes('回款')),'later successful persist re-sends the payment/audit from the failed attempt');
}

// DELETE: destructive confirmation-time integrity already re-resolves the live
// receivable/payment and month lock. The remaining durability gap is after that valid
// confirmation: deletion success is still optimistic relative to the cloud ACK.
{
  const {subject,row,calls,getConfirm}=makeRuntime('delete');
  subject.deleteReceivablePayment(row,row.payments[0]);
  const confirm=getConfirm();
  if(typeof confirm!=='function')throw new Error('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FAILED: delete confirmation callback missing');
  confirm();
  finding('delete-success-before-ack',row.payments.length===1&&row.payments[0].id==='pay-keep'&&calls.notify.some(message=>message.includes('回款流水已删除'))&&calls.fetch.length===0,'deleted ledger row and success notice exist before any cloud acknowledgement');
  await sleep(240);
  finding('delete-503-local-state',calls.fetch.length>=1&&row.payments.length===1&&row.paidAmount===10&&subject.auditLogs.length>0,'503 leaves failed deletion, recalculated paid total, and success audit in live memory');
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const saved=later?.financeReceivables?.find(r=>r.id===row.id);
  finding('delete-later-persist-resurrects',calls.fetch.length>=2&&saved?.payments?.length===1&&saved.payments[0]?.id==='pay-keep'&&later?.auditLogs?.some(a=>String(a.action).includes('回款')),'later successful persist re-sends the failed deletion/audit');
}

if(findings.length){
  throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}\n- ${findings.join('\n- ')}`);
}
console.log('BUSINESS_RECEIVABLE_PAYMENT_PERSISTENCE_ACK_PROBE_SAFE: save+delete=ack-before-success+rollback-safe');
