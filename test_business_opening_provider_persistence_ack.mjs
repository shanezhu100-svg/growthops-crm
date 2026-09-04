import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('saveOpeningProvider')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: final method not executable: ${error.message}`)}
if(typeof methods.saveOpeningProvider!=='function')throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: saveOpeningProvider not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_OPENING_PROVIDER_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

const policy=(overrides={})=>({id:'policy-1',effectiveDate:'2026-09-01',rebateRate:12.5,rebatePolicy:'standard',...overrides});
const contact=(overrides={})=>({id:'contact-1',name:'Alice',rebatePolicies:[policy()],...overrides});
const form=(overrides={})=>({id:null,name:'Provider A',contacts:[contact()],notes:'',...overrides});
const provider=(overrides={})=>({...form({id:'provider-1'}),...overrides});
const linkedDeal=(overrides={})=>({id:'deal-1',providerId:'provider-1',contactId:'contact-1',partnerName:'Provider Old',contactName:'Alice Old',contactInfo:'legacy',notes:'deal-before',...overrides});

function makeRuntime({kind,first='fail',withBarrier=true}){
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0,uid=0;
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
  const existing=kind==='edit'?provider({name:'Provider Old'}):null;
  const originalDeal=kind==='edit'?linkedDeal():null;
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},clients:[],openingProviders:existing?[clone(existing)]:[],openingDeals:originalDeal?[clone(originalDeal)]:[],financeCosts:[],auditLogs:[],backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    providerForm:kind==='edit'?form({id:'provider-1',name:'Provider Updated',contacts:[contact({name:'Alice Updated'})]}):form(),showProviderModal:true,
    canManageProviders:()=>true,accountUid:prefix=>`${prefix}-${++uid}`,normalizeOpeningProvider:value=>clone(value),
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:[],openingProviders:clone(subject.openingProviders),openingDeals:clone(subject.openingDeals),financeCosts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,existing:clone(existing),originalDeal:clone(originalDeal),resolveFirst:status=>gate?.resolve(response(status))};
}

async function waitForFirstFetch(calls){for(let i=0;i<20&&calls.fetch.length===0;i+=1)await sleep(5);eq(calls.fetch.length,1,'durable barrier must issue exactly one pending save before ACK')}
async function persistedRollback(calls){await sleep(240);ok(calls.fetch.length>=2,'rollback truth must itself reach serialized save queue');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}

// CREATE is reversible in memory while pending, but user-visible completion is held
// until the real adapter save ACKs.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});
  const initialForm=clone(subject.providerForm);
  const task=subject.saveOpeningProvider();
  ok(task&&typeof task.then==='function','create must expose ACK promise');
  eq(subject.openingProviders.length,1,'create tentative provider exists for serialization');
  ok(subject.showProviderModal,'create modal remains open before ACK');
  same(subject.providerForm,initialForm,'create form restored while ACK pending');
  eq(calls.notify.length,0,'create success notice held before ACK');
  await waitForFirstFetch(calls);
  const pending=parseState(calls.fetch[0]);
  eq((pending.openingProviders||[]).length,1,'pending create save contains tentative provider');
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful create uses one durable save');
  eq(subject.showProviderModal,false,'create modal closes only after ACK');
}

// EDIT likewise serializes the provider plus linked-deal display synchronization while
// keeping the editor open until the same save is acknowledged.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const initialForm=clone(subject.providerForm);
  const task=subject.saveOpeningProvider();
  ok(task&&typeof task.then==='function','edit must expose ACK promise');
  eq(subject.openingProviders[0]?.name,'Provider Updated','edit tentative provider exists while pending');
  eq(subject.openingDeals[0]?.partnerName,'Provider Updated','edit tentative linked provider name exists while pending');
  eq(subject.openingDeals[0]?.contactName,'Alice Updated','edit tentative linked contact name exists while pending');
  eq(subject.openingDeals[0]?.contactInfo,'','edit tentative linked legacy contact info is cleared');
  ok(subject.showProviderModal,'edit modal remains open before ACK');
  same(subject.providerForm,initialForm,'edit form restored while ACK pending');
  await waitForFirstFetch(calls);
  resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful edit uses one durable save');
  eq(subject.showProviderModal,false,'edit modal closes only after ACK');
}

// Failed CREATE removes only the attempted source/audit, persists rollback truth and
// cannot be resurrected by a later ordinary save.
{
  const {subject,calls}=makeRuntime({kind:'create',first:'fail'});
  const initialForm=clone(subject.providerForm);
  await subject.saveOpeningProvider();
  eq(subject.openingProviders.length,0,'failed create removes attempted provider');
  ok(!subject.auditLogs.some(a=>a.action==='新增开户商'),'failed create removes attempt audit');
  ok(subject.showProviderModal,'failed create keeps modal open');
  same(subject.providerForm,initialForm,'failed create restores form');
  ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed create explains durable failure');
  const rollback=await persistedRollback(calls);
  eq((rollback.openingProviders||[]).length,0,'create rollback cloud excludes attempted provider');
  ok(!(rollback.auditLogs||[]).some(a=>a.action==='新增开户商'),'create rollback cloud excludes attempt audit');
  const later=await laterPersist(subject,calls);
  eq((later.openingProviders||[]).length,0,'later persist cannot resurrect failed provider create');
  ok(!(later.auditLogs||[]).some(a=>a.action==='新增开户商'),'later persist cannot resurrect failed create audit');
}

// Failed EDIT restores both provider source and only the denormalized linked-deal fields
// changed by this attempt; rollback truth and later saves stay on the restored state.
{
  const {subject,calls,existing,originalDeal}=makeRuntime({kind:'edit',first:'fail'});
  const initialForm=clone(subject.providerForm);
  await subject.saveOpeningProvider();
  same(subject.openingProviders[0],existing,'failed edit restores provider exact prestate');
  same(subject.openingDeals[0],originalDeal,'failed edit restores linked deal exact prestate');
  ok(!subject.auditLogs.some(a=>a.action==='修改开户商资料'),'failed edit removes attempt audit');
  ok(subject.showProviderModal,'failed edit keeps modal open');
  same(subject.providerForm,initialForm,'failed edit restores form');
  const rollback=await persistedRollback(calls);
  same(rollback.openingProviders?.[0],existing,'edit rollback cloud restores provider');
  same(rollback.openingDeals?.[0],originalDeal,'edit rollback cloud restores linked deal');
  const later=await laterPersist(subject,calls);
  same(later.openingProviders?.[0],existing,'later persist cannot resurrect failed provider edit');
  same(later.openingDeals?.[0],originalDeal,'later persist cannot resurrect failed linked-deal rewrite');
  ok(!(later.auditLogs||[]).some(a=>a.action==='修改开户商资料'),'later persist cannot resurrect failed edit audit');
}

// CREATE rollback is attempt-scoped: unrelated provider/deal/audit appended while ACK
// is pending remain authoritative.
{
  const {subject,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});
  const task=subject.saveOpeningProvider();
  const otherProvider=provider({id:'provider-other',name:'Other Provider'}),otherDeal=linkedDeal({id:'deal-other',providerId:'provider-other'}),otherAudit={id:'audit-other',action:'并发审计'};
  subject.openingProviders.push(otherProvider);subject.openingDeals.push(otherDeal);subject.auditLogs.push(otherAudit);
  resolveFirst(503);await task;
  eq(subject.openingProviders.length,1,'failed create removes only attempted provider');
  ok(subject.openingProviders.includes(otherProvider),'unrelated provider survives create rollback');
  ok(subject.openingDeals.includes(otherDeal),'unrelated deal survives create rollback');
  ok(subject.auditLogs.includes(otherAudit),'unrelated audit survives create rollback');
}

// EDIT rollback likewise preserves unrelated live state and audits created after the
// attempt audit scope was captured.
{
  const {subject,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveOpeningProvider();
  const otherProvider=provider({id:'provider-other',name:'Other Provider'}),otherDeal=linkedDeal({id:'deal-other',providerId:'provider-other'}),otherAudit={id:'audit-other',action:'并发审计'};
  subject.openingProviders.push(otherProvider);subject.openingDeals.push(otherDeal);subject.auditLogs.push(otherAudit);
  resolveFirst(503);await task;
  ok(subject.openingProviders.includes(otherProvider),'unrelated provider survives edit rollback');
  ok(subject.openingDeals.includes(otherDeal),'unrelated deal survives edit rollback');
  ok(subject.auditLogs.includes(otherAudit),'unrelated audit survives edit rollback');
}

// Same-ID provider/deal replacements written while ACK is pending are newer truth and
// must never be overwritten by stale rollback.
{
  const {subject,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveOpeningProvider();
  const providerReplacement=provider({name:'Provider Concurrent'}),dealReplacement=linkedDeal({partnerName:'Provider Concurrent',contactName:'Contact Concurrent',contactInfo:'newer'});
  subject.openingProviders.splice(0,1,providerReplacement);subject.openingDeals.splice(0,1,dealReplacement);
  resolveFirst(503);await task;
  eq(subject.openingProviders[0],providerReplacement,'same-ID provider replacement remains authoritative');
  eq(subject.openingDeals[0],dealReplacement,'same-ID linked-deal replacement remains authoritative');
}

// On the same original linked-deal object, unrelated concurrent fields survive while
// the provider-controlled fields still roll back.
{
  const {subject,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveOpeningProvider();
  const row=subject.openingDeals[0];row.notes='concurrent-note';
  resolveFirst(503);await task;
  eq(row.partnerName,'Provider Old','attempt provider name rolls back on same deal object');
  eq(row.contactName,'Alice Old','attempt contact name rolls back on same deal object');
  eq(row.contactInfo,'legacy','attempt contact info rolls back on same deal object');
  eq(row.notes,'concurrent-note','unrelated concurrent deal field survives rollback');
}

// If a provider-controlled field itself receives a newer concurrent value, field-level
// compare-and-restore must preserve that newer value rather than restoring stale state.
{
  const {subject,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  const task=subject.saveOpeningProvider();
  const row=subject.openingDeals[0];row.partnerName='Provider Concurrent';
  resolveFirst(503);await task;
  eq(row.partnerName,'Provider Concurrent','newer provider-name field remains authoritative');
  eq(row.contactName,'Alice Old','untouched attempt contact-name field rolls back');
  eq(row.contactInfo,'legacy','untouched attempt contact-info field rolls back');
}

// Missing durability service fails closed for both create and edit without issuing a
// save or presenting successful completion.
for(const kind of ['create','edit']){
  const {subject,calls,existing,originalDeal}=makeRuntime({kind,first:'deferred',withBarrier:false});
  const initialForm=clone(subject.providerForm);
  const result=subject.saveOpeningProvider();
  eq(result,undefined,`${kind} missing barrier returns without success promise`);
  eq(calls.fetch.length,0,`${kind} missing barrier issues zero network saves`);
  ok(subject.showProviderModal,`${kind} missing barrier keeps modal open`);
  same(subject.providerForm,initialForm,`${kind} missing barrier restores form`);
  ok(calls.notify.some(m=>m.includes('持久化服务不可用')),`${kind} missing barrier explains unavailable durability service`);
  ok(!subject.auditLogs.some(a=>a.action==='新增开户商'||a.action==='修改开户商资料'),`${kind} missing barrier removes attempt audit`);
  if(kind==='create')eq(subject.openingProviders.length,0,'create missing barrier removes tentative provider');
  else{same(subject.openingProviders[0],existing,'edit missing barrier restores provider');same(subject.openingDeals[0],originalDeal,'edit missing barrier restores linked deal')}
}

console.log('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; create+edit=success-after-save-ack; failure=provider+linked-deal-fields+attempt-audit-rollback+rollback-persisted; later-persist=failed-operation-not-resurrected; concurrency=unrelated-state+same-id-provider/deal+field-level-replacement-preserved; missing-barrier=fail-closed');
