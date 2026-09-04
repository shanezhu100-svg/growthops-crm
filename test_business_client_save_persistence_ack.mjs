import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

const sideEffects=new Set(['persist','persistClientSaveBarrier','logAudit','notify','navigateTo','ensureAutomaticAssetCosts','ensureAutomaticReceivables','ensureClientFirstReceivable']);
const pureStubs=new Set(['localDateKey']);
const methodSources=new Map();
function collectMethod(name){
  if(methodSources.has(name)||sideEffects.has(name)||pureStubs.has(name))return;
  const source=extractMethod(name);methodSources.set(name,source);
  for(const match of source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)){
    const child=match[1];if(child!==name&&!sideEffects.has(child)&&!pureStubs.has(child))collectMethod(child);
  }
}
collectMethod('saveClient');
const context={Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,setTimeout,clearTimeout};
const methods={};
for(const [name,source] of methodSources){
  try{const parsed=vm.runInNewContext(`({${source}})`,context,{timeout:1000});methods[name]=parsed[name]}
  catch(error){throw new Error(`BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: unable to execute shipped ${name}: ${error.message}`)}
}
if(typeof methods.saveClient!=='function')throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: saveClient not executable');

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_CLIENT_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(row=>String(row?.id??'')===String(id)):undefined;
const clientRefs=(rows,id)=>Array.isArray(rows)?rows.filter(row=>String(row?.clientId??'')===String(id)):[];

function makeRuntime({kind='create',first='fail',withBarrier=true}={}){
  const calls={fetch:[],notify:[],navigate:[],hooks:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#client-form'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistClientSaveBarrier;
  const existing={id:'client-save-1',name:'Before Save',archived:false,status:'ACTIVE',platform:['TK'],billingMode:'FULL_MONTH',monthlyFee:100,currency:'USD',startDate:'2026-09-01',notes:'client-before',networkEnvironments:[],fbAccounts:[],tkAccounts:[{id:'old-tk'}],googleAccounts:[],instagramAccounts:[]};
  const survivor={id:'client-survivor',name:'Survivor',archived:false,status:'ACTIVE',billingMode:'MANUAL',monthlyFee:0,currency:'USD'};
  const lead={id:'lead-source',company:'Lead Source',stage:'QUALIFIED',nextFollowUp:'2026-09-10',convertedClientId:null,convertedAt:'',notes:'lead-before'};
  const unrelatedLead={id:'lead-survivor',stage:'WON',convertedClientId:'client-survivor',convertedAt:'2026-08-01T00:00:00.000Z'};
  const form=kind==='edit'?{...existing,name:'After Edit',monthlyFee:120}:{id:null,sourceLeadId:'lead-source',name:'Created Client',archived:false,status:'ACTIVE',platform:['TK'],billingMode:'FULL_MONTH',monthlyFee:500,currency:'USD',startDate:'2026-09-01',notes:'form-before',networkEnvironments:[],fbAccounts:[],tkAccounts:[{id:'tk-new',bcId:'bc-new',adAccountId:'ad-new',loginAccount:'login-new',loginPassword:'',twofa:''}],googleAccounts:[],instagramAccounts:[]};
  const initialSelections=kind==='create'?{
    selectedClientId:'old-client-selection',selectedAssetsClientId:'old-assets-selection',selectedSopClientId:'old-sop-selection',selectedAnalyticsClientId:'old-analytics-selection',selectedAdsClientId:'old-ads-selection',
  }:{selectedClientId:'client-save-1',selectedAssetsClientId:'client-save-1',selectedSopClientId:'client-save-1',selectedAnalyticsClientId:'client-save-1',selectedAdsClientId:'client-save-1'};
  Object.assign(subject,methods,{
    clients:kind==='edit'?[existing,survivor]:[survivor],leads:[lead,unrelatedLead],
    financeReceivables:[{id:'receivable-survivor',clientId:'client-survivor',source:'KEEP'}],financeCosts:[{id:'cost-survivor',clientId:'client-survivor',source:'KEEP'}],standaloneAlerts:[{id:'alert-survivor',clientId:'client-survivor'}],dismissedAlerts:[{id:'dismissed-survivor',clientId:'client-survivor'}],
    openingProviders:[],openingDeals:[],auditLogs:[{id:'audit-existing',action:'EXISTING',target:'keep'}],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    form,formDirty:true,currentPage:'client-form',currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},...initialSelections,
    localDateKey:()=> '2026-09-01',$nextTick:fn=>{if(typeof fn==='function')fn()},ensureDailyBackup:()=>{},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),navigateTo:(...args)=>calls.navigate.push(args),
    ensureClientFirstReceivable:client=>{calls.hooks.push('first');subject.financeReceivables.push({id:`first-${client.id}`,clientId:client.id,source:'FIRST'});return 1},
    ensureAutomaticReceivables:client=>{calls.hooks.push('receivable');subject.financeReceivables.push({id:`auto-r-${client.id}`,clientId:client.id,source:'AUTO'});return 1},
    ensureAutomaticAssetCosts:client=>{calls.hooks.push('cost');subject.financeCosts.push({id:`auto-c-${client.id}`,clientId:client.id,source:'AUTO'});return 1},
    collectBackupPayload:()=>({clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeReceivables:clone(subject.financeReceivables),financeCosts:clone(subject.financeCosts),standaloneAlerts:clone(subject.standaloneAlerts),dismissedAlerts:clone(subject.dismissedAlerts),auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,existing,lead,initialSelections:clone(initialSelections),resolveFirst:status=>gate?.resolve(response(status))};
}
async function waitFirstSave(calls){for(let i=0;i<40&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending durable save before ACK')}
async function waitRollback(calls){for(let i=0;i<40&&calls.fetch.length<2;i+=1)await sleep(10);ok(calls.fetch.length>=2,'failed ACK must enqueue rollback truth');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}
function successNotice(calls){return calls.notify.some(message=>/保存|创建|更新|客户/.test(message)&&!/未保存|失败|不可用/.test(message))}
function assertUnrelated(subject,label){
  ok(byId(subject.clients,'client-survivor'),`${label} preserves unrelated client`);
  ok(byId(subject.leads,'lead-survivor'),`${label} preserves unrelated lead`);
  ok(byId(subject.financeReceivables,'receivable-survivor'),`${label} preserves unrelated receivable`);
  ok(byId(subject.financeCosts,'cost-survivor'),`${label} preserves unrelated cost`);
  ok(subject.auditLogs.some(row=>row.id==='audit-existing'),`${label} preserves preexisting audit`);
}

// Create success: all three business helper hooks execute inside one durable unit,
// while success UI/navigation remains held until the real adapter ACKs the state.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});
  const task=subject.saveClient();ok(task&&typeof task.then==='function','create exposes ACK promise');
  await waitFirstSave(calls);
  eq(successNotice(calls),false,'create success notice held before ACK');eq(calls.navigate.length,0,'create navigation held before ACK');eq(subject.formDirty,true,'create form remains dirty while ACK is pending');
  for(const hook of ['first','receivable','cost'])ok(calls.hooks.includes(hook),`create executes ${hook} helper inside durability unit`);
  const pending=parseState(calls.fetch[0]);const created=(pending.clients||[]).find(row=>row.name==='Created Client');ok(created,'pending create state contains client');
  ok(clientRefs(pending.financeReceivables,created.id).length>0,'pending create state contains adapter-accepted generated receivable');
  ok(clientRefs(subject.financeCosts,created.id).length>0,'tentative local create contains generated cost before ACK');
  const pendingLead=byId(pending.leads,'lead-source');eq(pendingLead?.stage,'WON','pending create state converts source lead');eq(String(pendingLead?.convertedClientId),String(created.id),'pending create state links source lead');ok((pending.auditLogs||[]).some(row=>row.id==='audit-1'),'pending create state contains attempt audit');
  subject.form.notes='user-continued-edit';subject.formDirty=true;resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful create uses one durable save');ok(successNotice(calls),'create success notice emitted after ACK');ok(calls.navigate.some(args=>args[0]==='client-detail'),'create navigates after ACK');eq(subject.form.notes,'user-continued-edit','form edit made during ACK survives successful create');eq(subject.formDirty,true,'form remains dirty when user edits during create ACK');
}

// Edit success is likewise ACK-gated and preserves the final edited client in the
// single tentative cloud snapshot.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});const task=subject.saveClient();ok(task&&typeof task.then==='function','edit exposes ACK promise');await waitFirstSave(calls);
  eq(successNotice(calls),false,'edit success notice held before ACK');eq(calls.navigate.length,0,'edit navigation held before ACK');const pending=parseState(calls.fetch[0]);eq(byId(pending.clients,'client-save-1')?.name,'After Edit','pending edit state contains edited client');ok((pending.auditLogs||[]).some(row=>row.id==='audit-1'),'pending edit state contains attempt audit');resolveFirst(200);await task;
  eq(calls.fetch.length,1,'successful edit uses one durable save');ok(successNotice(calls),'edit success notice emitted after ACK');ok(calls.navigate.some(args=>args[0]==='client-detail'),'edit navigates after ACK');
}

// Failed create rolls back the complete attempt-owned local client/lead/finance/
// selection/audit state, persists rollback truth, and cannot be resurrected later.
{
  const {subject,calls,lead,initialSelections}=makeRuntime({kind:'create',first:'fail'});const task=subject.saveClient();if(task&&typeof task.then==='function')await task;
  const attempted=parseState(calls.fetch[0]);const created=(attempted.clients||[]).find(row=>row.name==='Created Client');ok(created,'failed create attempted cloud client exists');
  ok(!byId(subject.clients,created.id),'failed create removes attempt client locally');eq(lead.stage,'QUALIFIED','failed create restores source lead stage');eq(lead.convertedClientId,null,'failed create restores source lead client pointer');eq(lead.convertedAt,'','failed create restores source lead convertedAt');eq(lead.nextFollowUp,'2026-09-10','failed create restores source lead follow-up');
  eq(clientRefs(subject.financeReceivables,created.id).length,0,'failed create removes attempt receivables');eq(clientRefs(subject.financeCosts,created.id).length,0,'failed create removes attempt costs');for(const [key,value] of Object.entries(initialSelections))eq(subject[key],value,`failed create restores ${key}`);
  eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'failed create removes attempt audit by identity');assertUnrelated(subject,'failed create');ok(calls.notify.some(message=>/云端保存失败|未保存/.test(message)),'failed create reports durable failure');eq(calls.navigate.length,0,'failed create does not replay success navigation');
  const rollback=await waitRollback(calls);ok(!byId(rollback.clients,created.id),'rollback cloud excludes failed create client');eq(clientRefs(rollback.financeReceivables,created.id).length,0,'rollback cloud excludes failed create receivables');eq(byId(rollback.leads,'lead-source')?.stage,'QUALIFIED','rollback cloud restores source lead');eq((rollback.auditLogs||[]).some(row=>row.id==='audit-1'),false,'rollback cloud excludes failed create audit');
  const later=await laterPersist(subject,calls);ok(!byId(later.clients,created.id),'later persist cannot resurrect failed create client');eq((later.auditLogs||[]).some(row=>row.id==='audit-1'),false,'later persist cannot resurrect failed create audit');
}

// Failed edit restores only attempt-owned client/finance/audit changes and persists
// the restored pre-edit truth.
{
  const {subject,calls,existing}=makeRuntime({kind:'edit',first:'fail'});const before=clone(existing);const task=subject.saveClient();if(task&&typeof task.then==='function')await task;
  same(byId(subject.clients,'client-save-1'),before,'failed edit restores original client');eq(clientRefs(subject.financeReceivables,'client-save-1').length,0,'failed edit removes attempt receivables');eq(clientRefs(subject.financeCosts,'client-save-1').length,0,'failed edit removes attempt costs');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'failed edit removes attempt audit');assertUnrelated(subject,'failed edit');eq(calls.navigate.length,0,'failed edit does not navigate');
  const rollback=await waitRollback(calls);same(byId(rollback.clients,'client-save-1'),before,'failed edit rollback cloud restores original client');eq(clientRefs(rollback.financeReceivables,'client-save-1').length,0,'failed edit rollback cloud removes attempt receivables');const later=await laterPersist(subject,calls);same(byId(later.clients,'client-save-1'),before,'later persist cannot resurrect failed edit');
}

// Newer state created while create ACK is pending wins over rollback. This includes
// same-ID client/finance replacements, lead fields, selections, form edits and audits.
{
  const {subject,calls,lead,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});const task=subject.saveClient();await waitFirstSave(calls);
  const attemptClient=subject.clients.find(row=>row.name==='Created Client');ok(attemptClient,'concurrency create has tentative client');const id=attemptClient.id;const clientReplacement={...clone(attemptClient),name:'Concurrent Client Replacement',notes:'replacement'};subject.clients.splice(subject.clients.indexOf(attemptClient),1,clientReplacement);
  lead.stage='CONCURRENT_STAGE';lead.convertedClientId='concurrent-client';lead.convertedAt='2026-09-04T08:00:00.000Z';lead.nextFollowUp='2026-09-30';
  const attemptReceivable=clientRefs(subject.financeReceivables,id)[0];if(attemptReceivable){const replacement={...clone(attemptReceivable),source:'CONCURRENT_RECEIVABLE'};subject.financeReceivables.splice(subject.financeReceivables.indexOf(attemptReceivable),1,replacement)}
  const attemptCost=clientRefs(subject.financeCosts,id)[0];if(attemptCost){const replacement={...clone(attemptCost),source:'CONCURRENT_COST'};subject.financeCosts.splice(subject.financeCosts.indexOf(attemptCost),1,replacement)}
  subject.selectedClientId='concurrent-selection';subject.selectedAssetsClientId='concurrent-assets';subject.form.notes='concurrent-form-edit';subject.formDirty=true;const concurrentAudit={id:'audit-concurrent',action:'CONCURRENT',target:'keep'};subject.auditLogs.push(concurrentAudit);
  resolveFirst(503);await task;
  eq(byId(subject.clients,id)?.name,'Concurrent Client Replacement','failed create preserves same-ID client replacement');eq(lead.stage,'CONCURRENT_STAGE','failed create preserves concurrent lead stage');eq(lead.convertedClientId,'concurrent-client','failed create preserves concurrent lead pointer');if(attemptReceivable)eq(byId(subject.financeReceivables,attemptReceivable.id)?.source,'CONCURRENT_RECEIVABLE','failed create preserves same-ID receivable replacement');if(attemptCost)eq(byId(subject.financeCosts,attemptCost.id)?.source,'CONCURRENT_COST','failed create preserves same-ID cost replacement');
  eq(subject.selectedClientId,'concurrent-selection','failed create preserves concurrent client selection');eq(subject.selectedAssetsClientId,'concurrent-assets','failed create preserves concurrent assets selection');eq(subject.form.notes,'concurrent-form-edit','failed create preserves concurrent form edit');eq(subject.formDirty,true,'failed create preserves dirty form after concurrent edit');ok(subject.auditLogs.includes(concurrentAudit),'failed create preserves unrelated concurrent audit');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'failed create still removes attempt audit');
  const rollback=await waitRollback(calls);eq(byId(rollback.clients,id)?.name,'Concurrent Client Replacement','rollback cloud preserves same-ID client replacement');eq(byId(rollback.leads,'lead-source')?.stage,'CONCURRENT_STAGE','rollback cloud preserves concurrent lead edit');eq((rollback.auditLogs||[]).some(row=>row.id==='audit-concurrent'),true,'rollback cloud preserves concurrent audit');eq((rollback.auditLogs||[]).some(row=>row.id==='audit-1'),false,'rollback cloud excludes attempt audit');
}

// Field-level compare-and-restore on edit must not overwrite a newer edit applied to
// the exact same live client object while the cloud ACK is pending.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});const task=subject.saveClient();await waitFirstSave(calls);const live=byId(subject.clients,'client-save-1');live.name='Concurrent Same-Object Edit';live.monthlyFee=333;subject.form.notes='typing-during-ack';subject.formDirty=true;subject.auditLogs.push({id:'audit-edit-concurrent',action:'CONCURRENT_EDIT'});resolveFirst(503);await task;
  eq(byId(subject.clients,'client-save-1')?.name,'Concurrent Same-Object Edit','failed edit preserves concurrent same-object name');eq(byId(subject.clients,'client-save-1')?.monthlyFee,333,'failed edit preserves concurrent same-object monthly fee');eq(subject.form.notes,'typing-during-ack','failed edit preserves concurrent form input');eq(subject.formDirty,true,'failed edit concurrent form remains dirty');ok(subject.auditLogs.some(row=>row.id==='audit-edit-concurrent'),'failed edit preserves concurrent audit');eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,'failed edit removes only attempt audit');const rollback=await waitRollback(calls);eq(byId(rollback.clients,'client-save-1')?.name,'Concurrent Same-Object Edit','rollback cloud preserves concurrent same-object edit');
}

// Missing durability authority is fail-closed for both create and edit: no network,
// no success navigation, and complete local rollback.
for(const kind of ['create','edit']){
  const {subject,calls,existing,lead}=makeRuntime({kind,withBarrier:false,first:'deferred'});const beforeClient=clone(existing),beforeLead=clone(lead);const result=subject.saveClient();if(result&&typeof result.then==='function')await result;await sleep(20);
  eq(calls.fetch.length,0,`${kind} missing barrier performs zero network`);eq(calls.navigate.length,0,`${kind} missing barrier performs zero navigation`);ok(calls.notify.some(message=>/持久化服务不可用|未保存/.test(message)),`${kind} missing barrier explains fail-closed save`);eq(subject.auditLogs.some(row=>row.id==='audit-1'),false,`${kind} missing barrier removes attempt audit`);
  if(kind==='create'){eq(subject.clients.some(row=>row.name==='Created Client'),false,'create missing barrier removes tentative client');same(byId(subject.leads,'lead-source'),beforeLead,'create missing barrier restores source lead')}else same(byId(subject.clients,'client-save-1'),beforeClient,'edit missing barrier restores original client');
}

console.log('BUSINESS_CLIENT_SAVE_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; create+edit=single-save-success-after-ACK; failure=client+lead+finance+selection+attempt-audit-rollback+rollback-persisted; later-persist=failed-save-not-resurrected; concurrency=same-id+field-level+finance-replacement+selection+form-edit+unrelated-audit-preserved; helper-persists=collapsed; missing-barrier=fail-closed');