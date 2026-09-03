import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
const toggle=vm.runInNewContext(`({${extract('toggleFinanceMonthLock')}})`,{Date,Math,Number,String,Object,Array,JSON,Set},{timeout:1000}).toggleFinanceMonthLock;
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const findings=[];

function parseSave(call){
  const body=JSON.parse(call.body||'{}');
  if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);
  return body.args?.p_state;
}
function makeRuntime({locked}){
  const month='2026-09';
  const calls={fetch:[],notify:[]};
  let confirmAction=null,auditId=0,saveAttempt=0;
  const subject={};
  const existingLock={lockedAt:'2026-09-01T00:00:00.000Z',lockedBy:'Admin',snapshotAt:'2026-09-01T00:00:00.000Z'};
  const existingSnapshot={createdAt:'2026-09-01T00:00:00.000Z',income:123};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});
    saveAttempt+=1;
    if(saveAttempt===1)return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_MONTH_LOCK_SAVE_FAILED'})};
    return {ok:true,status:200,json:async()=>({revision:saveAttempt})};
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    toggleFinanceMonthLock:toggle,
    currentUser:locked?{id:'admin',name:'Admin',role:'ADMIN',enabled:true}:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},
    financeMonthLocks:locked?{[month]:structuredClone(existingLock)}:{},
    financeMonthSnapshots:locked?{[month]:structuredClone(existingSnapshot)}:{},
    auditLogs:[],backupSnapshots:[],clients:[],
    canManageFinance:()=>true,
    isMonthLocked:key=>Boolean(subject.financeMonthLocks[key]),
    ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureDailyBackup:()=>{},
    runFinanceMonthCheck:()=>({issues:[]}),getFinanceMonthCheck:()=>({issues:[]}),
    buildFinanceMonthSnapshot:()=>({createdAt:'2026-09-03T00:00:00.000Z',income:456}),
    askConfirm:(_config,action)=>{confirmAction=action;},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action,target};subject.auditLogs.push(row);return row;},
    notify:message=>calls.notify.push(String(message)),
    collectBackupPayload:()=>({clients:[],financeMonthLocks:structuredClone(subject.financeMonthLocks),financeMonthSnapshots:structuredClone(subject.financeMonthSnapshots),auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,calls,month,existingLock,existingSnapshot,getConfirm:()=>confirmAction};
}

{
  const {subject,calls,month,getConfirm}=makeRuntime({locked:false});
  subject.toggleFinanceMonthLock(month);
  const confirm=getConfirm();if(typeof confirm!=='function')throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: lock confirmation missing');
  confirm();
  if(calls.fetch.length===0&&calls.notify.some(message=>message.includes('已完成月结')))findings.push('lock: success notice is emitted before any durable save acknowledgement');
  await sleep(240);
  if(subject.financeMonthLocks[month]&&subject.financeMonthSnapshots[month]&&subject.auditLogs.some(row=>row.action==='完成财务月结'))findings.push('lock: failed cloud save leaves local lock, frozen snapshot, and success audit in memory');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  if(later?.financeMonthLocks?.[month]&&later?.auditLogs?.some(row=>row.action==='完成财务月结'))findings.push('lock: later ordinary persist can resurrect the previously failed lock operation');
}

{
  const {subject,calls,month,getConfirm}=makeRuntime({locked:true});
  subject.toggleFinanceMonthLock(month);
  const confirm=getConfirm();if(typeof confirm!=='function')throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FAILED: unlock confirmation missing');
  confirm();
  if(calls.fetch.length===0&&calls.notify.some(message=>message.includes('已解锁')))findings.push('unlock: success notice is emitted before any durable save acknowledgement');
  await sleep(240);
  if(!subject.financeMonthLocks[month]&&!subject.financeMonthSnapshots[month]&&subject.auditLogs.some(row=>row.action==='解除财务月结'))findings.push('unlock: failed cloud save leaves local month protection removed and success audit in memory');
  subject.persist();await sleep(240);
  const later=parseSave(calls.fetch.at(-1));
  if(!later?.financeMonthLocks?.[month]&&later?.auditLogs?.some(row=>row.action==='解除财务月结'))findings.push('unlock: later ordinary persist can resurrect the previously failed unlock operation');
}

if(findings.length)throw new Error(`BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(' | ')}`);
console.log('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_PROBE_SAFE');
