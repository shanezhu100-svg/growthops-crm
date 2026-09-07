import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let saveLead;
try{saveLead=vm.runInNewContext(`({${extractMethod('saveLead')}}).saveLead`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: final saveLead not executable: ${error.message}`)}
if(typeof saveLead!=='function')throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: saveLead not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LEAD_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(row=>String(row?.id??'')===String(id)):undefined;

function makeRuntime({kind='create',first='fail',withBarrier=true}={}){
  const calls={fetch:[],notify:[]};const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#leads'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistLeadSaveBarrier;
  const existing={id:'lead-save-1',company:'Before Lead',contact:'Old',stage:'QUALIFIED',source:'网站询盘',platformInterest:'FB+TK',budgetCurrency:'USD',expectedBudget:100,quoteCurrency:'USD',adQuote:50,nextFollowUp:'2026-09-10',convertedClientId:null,convertedAt:'',createdAt:'2026-09-01',notes:'before-note'};
  const survivor={id:'lead-survivor',company:'Survivor',contact:'Keep',stage:'NEW',createdAt:'2026-09-01'};
  const form=kind==='edit'?{...existing,company:'After Lead Edit',expectedBudget:'120'}:{id:null,company:'Created Lead',contact:'New',stage:'NEW',source:'网站询盘',platformInterest:'TK',budgetCurrency:'USD',expectedBudget:'500',quoteCurrency:'USD',adQuote:'0',nextFollowUp:'2026-09-12',convertedClientId:null,convertedAt:'',notes:'create-form'};
  Object.assign(subject,{
    saveLead,leads:kind==='edit'?[existing,survivor]:[survivor],clients:[],financeReceivables:[],financeCosts:[],openingProviders:[],openingDeals:[],standaloneAlerts:[],dismissedAlerts:[],
    auditLogs:[{id:'audit-existing',action:'EXISTING',target:'keep'}],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    leadForm:clone(form),showLeadModal:true,leadPoolFilter:'ACTIVE',leadQuickFilter:'ALL',
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},accountUid:()=> 'lead-created-1',localDateKey:()=> '2026-09-07',leadStageText:v=>String(v),ensureDailyBackup:()=>{},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},notify:m=>calls.notify.push(String(m)),
    collectBackupPayload:()=>({clients:[],leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,existing,survivor,resolveFirst:status=>gate?.resolve(response(status))};
}
async function waitFirstSave(calls){for(let i=0;i<40&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending durable save before ACK')}
async function waitRollback(calls){for(let i=0;i<40&&calls.fetch.length<2;i+=1)await sleep(10);ok(calls.fetch.length>=2,'failed ACK must enqueue rollback truth');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}
function successNotice(calls){return calls.notify.some(message=>message.includes('已保存')&&!/未保存|失败/.test(message))}
function assertBaseUnrelated(subject,label){ok(byId(subject.leads,'lead-survivor'),`${label} preserves unrelated lead`);ok(subject.auditLogs.some(row=>row.id==='audit-existing'),`${label} preserves preexisting audit`)}

// Create success: the exact lead + audit reaches one real cloud save while success UI
// remains reversible. User edits to the form while awaiting ACK are not discarded.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});
  const task=subject.saveLead();ok(task&&typeof task.then==='function','create exposes ACK promise');
  await waitFirstSave(calls);
  eq(subject.showLeadModal,true,'create modal stays open before ACK');eq(subject.leadPoolFilter,'ACTIVE','create pool UI held before ACK');eq(successNotice(calls),false,'create success notice held before ACK');
  const pending=parseState(calls.fetch[0]);ok(byId(pending.leads,'lead-created-1'),'pending create state contains lead');ok((pending.auditLogs||[]).some(row=>row.id==='audit-1'),'pending create state contains attempt audit');
  subject.leadForm.notes='typed-while-saving';
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful create uses one durable save');eq(subject.showLeadModal,false,'create closes modal after ACK');eq(subject.leadPoolFilter,'ACTIVE','create final pool is ACTIVE after ACK');ok(successNotice(calls),'create success notice emitted after ACK');eq(subject.leadForm.notes,'typed-while-saving','create preserves form edit made during ACK');
}

// Edit success is ACK-gated and the tentative cloud snapshot already contains the
// edited row and its attempt audit.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveLead();ok(task&&typeof task.then==='function','edit exposes ACK promise');await waitFirstSave(calls);
  eq(subject.showLeadModal,true,'edit modal stays open before ACK');eq(successNotice(calls),false,'edit success notice held before ACK');
  const pending=parseState(calls.fetch[0]);eq(byId(pending.leads,'lead-save-1')?.company,'After Lead Edit','pending edit state contains edited lead');ok((pending.auditLogs||[]).some(row=>row.id==='audit-1'),'pending edit state contains attempt audit');
  resolveFirst(200);await task;eq(calls.fetch.length,1,'successful edit uses one durable save');eq(subject.showLeadModal,false,'edit closes modal after ACK');ok(successNotice(calls),'edit success notice emitted after ACK');
}

// Failed create removes only attempt-owned lead/audit state, persists rollback truth,
// and ordinary persistence cannot resurrect the failed operation.
{
  const {subject,calls}=makeRuntime({kind:'create',first:'fail'});
  const task=subject.saveLead();if(task&&typeof task.then==='function')await task;
  ok(!byId(subject.leads,'lead-created-1'),'failed create removes attempt lead locally');eq(subject.auditLogs.filter(row=>row.id==='audit-1').length,0,'failed create removes attempt audit');assertBaseUnrelated(subject,'failed create');eq(subject.showLeadModal,true,'failed create keeps modal open');ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed create reports durable failure');
  const rollback=await waitRollback(calls);ok(!byId(rollback.leads,'lead-created-1'),'rollback cloud excludes failed create lead');eq((rollback.auditLogs||[]).filter(row=>row.id==='audit-1').length,0,'rollback cloud excludes failed create audit');
  const later=await laterPersist(subject,calls);ok(!byId(later.leads,'lead-created-1'),'later persist cannot resurrect failed create lead');eq((later.auditLogs||[]).filter(row=>row.id==='audit-1').length,0,'later persist cannot resurrect failed create audit');
}

// Failed edit restores the pre-save row and durable cloud truth.
{
  const {subject,calls,existing}=makeRuntime({kind:'edit',first:'fail'});const before=clone(existing);
  const task=subject.saveLead();if(task&&typeof task.then==='function')await task;
  same(byId(subject.leads,'lead-save-1'),before,'failed edit restores original lead');eq(subject.auditLogs.filter(row=>row.id==='audit-1').length,0,'failed edit removes attempt audit');assertBaseUnrelated(subject,'failed edit');
  const rollback=await waitRollback(calls);same(byId(rollback.leads,'lead-save-1'),before,'rollback cloud restores original lead');
  const later=await laterPersist(subject,calls);same(byId(later.leads,'lead-save-1'),before,'later persist cannot resurrect failed edit');
}

// Field-level rollback preserves newer edits to the original object, unrelated audit,
// filter/modal changes, and form edits made while the failed ACK was pending.
{
  const {subject,calls,existing,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveLead();await waitFirstSave(calls);
  existing.company='Concurrent Company';existing.notes='concurrent-note';
  const concurrentAudit={id:'audit-concurrent',action:'CONCURRENT'};subject.auditLogs.push(concurrentAudit);
  subject.leadPoolFilter='WON';subject.leadQuickFilter='HIGH';subject.showLeadModal=false;subject.leadForm.contact='typed-concurrently';
  resolveFirst(503);await task;
  eq(existing.company,'Concurrent Company','field-level rollback preserves concurrent company');eq(existing.notes,'concurrent-note','field-level rollback preserves concurrent notes');eq(subject.auditLogs.includes(concurrentAudit),true,'rollback preserves concurrent audit');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'rollback removes only attempt audit');eq(subject.leadPoolFilter,'WON','rollback preserves concurrent pool filter');eq(subject.leadQuickFilter,'HIGH','rollback preserves concurrent quick filter');eq(subject.showLeadModal,false,'rollback preserves concurrent modal state');eq(subject.leadForm.contact,'typed-concurrently','rollback preserves concurrent form edit');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,'lead-save-1')?.company,'Concurrent Company','rollback cloud preserves concurrent lead field');ok((rollback.auditLogs||[]).some(row=>row.id==='audit-concurrent'),'rollback cloud preserves concurrent audit');
}

// A whole-object same-ID replacement is newer authority and cannot be overwritten by
// rollback of the stale edit object.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});const task=subject.saveLead();await waitFirstSave(calls);
  const replacement={id:'lead-save-1',company:'Replacement Authority',stage:'WON',notes:'replacement'};const at=subject.leads.findIndex(row=>row.id==='lead-save-1');subject.leads.splice(at,1,replacement);
  resolveFirst(503);await task;eq(byId(subject.leads,'lead-save-1'),replacement,'same-ID replacement remains authoritative locally');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,'lead-save-1')?.company,'Replacement Authority','same-ID replacement reaches rollback cloud truth');
}

// Missing durability primitive must fail closed before any network write or false success.
{
  const {subject,calls}=makeRuntime({kind:'create',first:'fail',withBarrier:false});const task=subject.saveLead();if(task&&typeof task.then==='function')await task;await sleep(220);
  eq(calls.fetch.length,0,'missing barrier performs zero network saves');ok(!byId(subject.leads,'lead-created-1'),'missing barrier rolls back tentative lead');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'missing barrier rolls back attempt audit');eq(subject.showLeadModal,true,'missing barrier keeps modal open');eq(successNotice(calls),false,'missing barrier emits no success notice');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier explains fail-closed state');
}

console.log('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; create+edit=single-save-success-after-ACK; failure=lead+attempt-audit-rollback+rollback-persisted; later-persist=failed-save-not-resurrected; concurrency=same-id+field-level+filter+modal+form-edit+unrelated-audit-preserved; missing-barrier=fail-closed');
