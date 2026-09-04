import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
let methods;
try{methods=vm.runInNewContext(`({${extract('saveReconciliation')},${extract('voidReconciliation')}})`,{Date,Math,Number,String,Object,Array,JSON,Set},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: final methods not executable: ${error.message}`);}
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const findings=[];

function parseSave(call){
  if(!call)throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: missing save call');
  const body=JSON.parse(call.body||'{}');
  if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);
  return body.args?.p_state;
}

function makeRuntime({mode}){
  const calls={fetch:[],notify:[]};
  const subject={};
  let confirmAction=null,saveAttempt=0,auditId=0;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});
    saveAttempt+=1;
    if(saveAttempt===1)return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_RECONCILIATION_SAVE_FAILED'})};
    return {ok:true,status:200,json:async()=>({revision:saveAttempt})};
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

  const matchingActual={providerId:'provider-1',contactId:'contact-1',settlementMonth:'2026-09',currency:'USD',actualRebate:8};
  const option={providerId:'provider-1',contactId:'contact-1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const existingRec={id:'recon-existing',providerId:'provider-1',contactId:'contact-1',providerName:'Agency',contactName:'Alice',settlementMonth:'2026-09',currency:'USD',confirmedSpend:100,actualRebate:8,status:'CONFIRMED'};
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},
    clients:[],backupSnapshots:[],auditLogs:[],financeMonthLocks:{},financeMonthSnapshots:{},
    financeReconciliations:mode==='void'?[existingRec]:[],
    financeActualRebates:[matchingActual],
    reconciliationSelectedOption:option,
    reconciliationForm:{id:'',settlementMonth:'2026-09',currency:'USD',confirmedSpend:'120',actualRebate:'12',confirmedDate:'2026-09-30',note:'checked'},
    reconciliationSystemSpend:118,reconciliationExpectedRebate:11,showReconciliationModal:true,
    assertMonthUnlocked:()=>true,
    accountUid:()=> 'recon-new',localDateKey:()=> '2026-09-30',formatMoney:(value,currency)=>`${currency||'USD'}:${value}`,
    askConfirm:(_config,action)=>{confirmAction=action;},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action,target};subject.auditLogs.push(row);return row;},
    notify:message=>calls.notify.push(String(message)),
    ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:[],financeReconciliations:structuredClone(subject.financeReconciliations),financeActualRebates:structuredClone(subject.financeActualRebates),financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,calls,existingRec,matchingActual,getConfirm:()=>confirmAction};
}

// Confirmation of actual provider rebate changes profit accounting, but currently
// announces success before the debounced cloud save is durable.
{
  const {subject,calls}=makeRuntime({mode:'save'});
  subject.saveReconciliation();
  if(calls.fetch.length===0&&calls.notify.some(message=>message.includes('对账已确认')))findings.push('save: success notice is emitted before any durable save acknowledgement');
  await sleep(240);
  if(subject.financeReconciliations.some(r=>r.status==='CONFIRMED')&&subject.auditLogs.some(row=>row.action==='代理商返点对账'))findings.push('save: failed cloud save leaves confirmed reconciliation and success audit in memory');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  if(later?.financeReconciliations?.some(r=>r.status==='CONFIRMED')&&later?.auditLogs?.some(row=>row.action==='代理商返点对账'))findings.push('save: later ordinary persist can resurrect the previously failed reconciliation confirmation');
}

// Voiding a confirmed reconciliation removes actual rebate from profit accounting;
// it has the symmetric durability gap after confirmation.
{
  const {subject,calls,existingRec,getConfirm}=makeRuntime({mode:'void'});
  subject.voidReconciliation({providerName:'Agency',contactName:'Alice',record:existingRec});
  const confirm=getConfirm();if(typeof confirm!=='function')throw new Error('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FAILED: void confirmation missing');
  confirm();
  if(calls.fetch.length===0&&calls.notify.some(message=>message.includes('对账已撤销')))findings.push('void: success notice is emitted before any durable save acknowledgement');
  await sleep(240);
  if(existingRec.status==='VOID'&&subject.financeActualRebates.length===0&&subject.auditLogs.some(row=>row.action==='撤销代理商返点对账'))findings.push('void: failed cloud save leaves local reconciliation voided, actual rebate removed, and success audit in memory');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  if(later?.financeReconciliations?.some(r=>r.id==='recon-existing'&&r.status==='VOID')&&later?.auditLogs?.some(row=>row.action==='撤销代理商返点对账'))findings.push('void: later ordinary persist can resurrect the previously failed reconciliation void');
}

if(findings.length)throw new Error(`BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(' | ')}`);
console.log('BUSINESS_RECONCILIATION_PERSISTENCE_ACK_PROBE_SAFE');
