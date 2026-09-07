import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
    if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let deleteLead;
try{deleteLead=vm.runInNewContext(`({${extractMethod('deleteLead')}}).deleteLead`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: final deleteLead not executable: ${error.message}`)}
if(typeof deleteLead!=='function')throw new Error('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: deleteLead not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LEAD_DELETE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(row=>String(row?.id??'')===String(id)):undefined;
const countId=(rows,id)=>Array.isArray(rows)?rows.filter(row=>String(row?.id??'')===String(id)).length:0;

function makeRuntime({first='fail',withBarrier=true}={}){
  const calls={fetch:[],notify:[],confirm:[]};const subject={};let saveAttempt=0,auditId=0,confirmCallback=null;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#leads'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistLeadDeleteBarrier;
  const target={id:'lead-delete-1',company:'Delete Me',contact:'Owner',stage:'QUALIFIED',notes:'original'};
  const survivor={id:'lead-survivor',company:'Survivor',stage:'NEW'};
  Object.assign(subject,{
    deleteLead,leads:[target,survivor],clients:[],financeReceivables:[],financeCosts:[],openingProviders:[],openingDeals:[],standaloneAlerts:[],dismissedAlerts:[],
    auditLogs:[{id:'audit-existing',action:'EXISTING'}],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},ensureDailyBackup:()=>{},
    askConfirm:(spec,callback)=>{calls.confirm.push(spec);confirmCallback=callback},
    logAudit:(action,targetText)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(targetText)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),
    collectBackupPayload:()=>({clients:[],leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,target,survivor,getConfirm:()=>confirmCallback,resolveFirst:status=>gate?.resolve(response(status))};
}
async function waitFirstSave(calls){for(let i=0;i<40&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending durable save before ACK')}
async function waitRollback(calls){for(let i=0;i<40&&calls.fetch.length<2;i+=1)await sleep(10);ok(calls.fetch.length>=2,'failed ACK must enqueue rollback truth');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}
function successNotice(calls){return calls.notify.some(message=>message.includes('已删除')&&!/未保存|失败/.test(message))}

// Confirmation-time liveness from the destructive-confirmation hardening must survive
// the durability wrapper: a row removed before confirmation is not deleted/audited again.
{
  const {subject,calls,target,getConfirm}=makeRuntime({first:'deferred'});
  subject.deleteLead(target);eq(calls.confirm.length,1,'delete asks for confirmation once');
  subject.leads=subject.leads.filter(row=>row.id!==target.id);
  const task=getConfirm()();if(task&&typeof task.then==='function')await task;
  eq(calls.fetch.length,0,'stale confirmation performs no durable save');eq(subject.auditLogs.length,1,'stale confirmation creates no audit');ok(calls.notify.some(m=>m.includes('状态已变化')),'stale confirmation reports live-state drift');
}

// Successful delete reaches exactly one cloud save containing the deletion + audit,
// while destructive success messaging is withheld until that save is acknowledged.
{
  const {subject,calls,target,getConfirm,resolveFirst}=makeRuntime({first:'deferred'});
  subject.deleteLead(target);eq(calls.fetch.length,0,'opening confirmation does not save');
  const task=getConfirm()();ok(task&&typeof task.then==='function','confirmed delete exposes ACK promise');await waitFirstSave(calls);
  ok(!byId(subject.leads,target.id),'target removed locally while ACK pending');ok(subject.auditLogs.some(row=>row.id==='audit-1'),'attempt audit exists while ACK pending');eq(successNotice(calls),false,'delete success notice held before ACK');
  const pending=parseState(calls.fetch[0]);ok(!byId(pending.leads,target.id),'pending cloud state contains deletion');ok((pending.auditLogs||[]).some(row=>row.id==='audit-1'),'pending cloud state contains delete audit');
  resolveFirst(200);await task;eq(calls.fetch.length,1,'successful delete uses one durable save');ok(successNotice(calls),'success notice emitted after ACK');ok(byId(subject.leads,'lead-survivor'),'successful delete preserves unrelated lead');
}

// Failed delete restores only the deleted lead and removes only this attempt's audit,
// then persists rollback truth so later writes cannot resurrect the failed deletion.
{
  const {subject,calls,target,getConfirm}=makeRuntime({first:'fail'});
  subject.deleteLead(target);const task=getConfirm()();if(task&&typeof task.then==='function')await task;
  ok(byId(subject.leads,target.id),'failed delete restores target locally');eq(countId(subject.leads,target.id),1,'failed delete restores target exactly once');ok(byId(subject.leads,'lead-survivor'),'failed delete preserves unrelated lead');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'failed delete removes attempt audit');ok(subject.auditLogs.some(row=>row.id==='audit-existing'),'failed delete preserves existing audit');eq(successNotice(calls),false,'failed delete emits no false success');ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed delete reports durable failure');
  const rollback=await waitRollback(calls);ok(byId(rollback.leads,target.id),'rollback cloud restores target');eq((rollback.auditLogs||[]).some(row=>row.id==='audit-1'),false,'rollback cloud removes failed delete audit');
  const later=await laterPersist(subject,calls);ok(byId(later.leads,target.id),'later persistence keeps restored target');
}

// A newer same-ID replacement created while the delete ACK is pending is authoritative.
// Failure rollback must not put the stale deleted object back on top of it.
{
  const {subject,calls,target,getConfirm,resolveFirst}=makeRuntime({first:'deferred'});
  subject.deleteLead(target);const task=getConfirm()();await waitFirstSave(calls);
  const replacement={id:target.id,company:'Replacement Authority',stage:'WON',notes:'newer'};subject.leads.unshift(replacement);
  const concurrentAudit={id:'audit-concurrent',action:'CONCURRENT'};subject.auditLogs.push(concurrentAudit);
  resolveFirst(503);await task;
  eq(byId(subject.leads,target.id),replacement,'same-ID replacement remains authoritative locally');eq(countId(subject.leads,target.id),1,'rollback does not duplicate same-ID lead');ok(subject.auditLogs.includes(concurrentAudit),'rollback preserves concurrent audit');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'rollback removes only delete attempt audit');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,target.id)?.company,'Replacement Authority','same-ID replacement reaches rollback cloud truth');ok((rollback.auditLogs||[]).some(row=>row.id==='audit-concurrent'),'rollback cloud preserves concurrent audit');
}

// Missing durability primitive fails closed: confirmation may tentatively execute, but
// the deleted row is restored locally and no success/network write is allowed.
{
  const {subject,calls,target,getConfirm}=makeRuntime({first:'fail',withBarrier:false});
  subject.deleteLead(target);const task=getConfirm()();if(task&&typeof task.then==='function')await task;await sleep(220);
  eq(calls.fetch.length,0,'missing barrier performs zero network saves');ok(byId(subject.leads,target.id),'missing barrier restores target');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'missing barrier removes attempt audit');eq(successNotice(calls),false,'missing barrier emits no success notice');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier explains fail-closed state');
}

console.log('BUSINESS_LEAD_DELETE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; confirmation=live-record-re-resolved; success=single-save+notice-after-ACK; failure=lead+attempt-audit-rollback+rollback-persisted; concurrency=same-id-replacement+unrelated-audit-preserved; missing-barrier=fail-closed');
