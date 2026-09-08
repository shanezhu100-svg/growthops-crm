import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);if(!match)throw new Error(`BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }throw new Error(`BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}
const names=['saveExternalAsset','deleteExternalAsset','saveMediaTool','deleteMediaTool','saveReminderType','deleteReminderType'];
let methods;
try{methods=vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: final methods not executable: ${error.message}`)}
for(const name of names)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: ${name} not executable`);

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const same=(actual,expected,label)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_RESOURCE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(row=>String(row?.id??'')===String(id)):undefined;
const byKey=(rows,key)=>Array.isArray(rows)?rows.find(row=>String(row?.key??'')===String(key)):undefined;

function makeRuntime({kind,mode='create',first='fail',withBarrier=true}={}){
  const calls={fetch:[],notify:[]};const subject={};let saveAttempt=0,auditId=0,resetCount=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#assets'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistResourceCatalogBarrier;

  const asset={id:'g1',accountName:'Google Old',loginAccount:'old-login',note:'before'};
  const client={id:'c1',name:'Client One',googleAccounts:[asset],instagramAccounts:[]};
  const tool={id:'t1',name:'Tool Old',bindings:['c1'],seats:1,loginPassword:'',note:'before'};
  const reminder={key:'CUSTOM_1',name:'Reminder Old',system:false};
  const externalAssetForm=mode==='edit'?{id:'g1',accountName:'Google New',loginAccount:'new-login',note:'after'}:{id:null,accountName:'Google Created',loginAccount:'created-login',note:'new'};
  const toolForm=mode==='edit'?{id:'t1',name:'Tool New',bindings:['c1'],seats:2,loginPassword:'',note:'after'}:{id:null,name:'Tool Created',bindings:['c1'],seats:2,loginPassword:'',note:'new'};
  const reminderTypeForm=mode==='edit'?{key:'CUSTOM_1',name:'Reminder New'}:{key:'',name:'Reminder Created'};
  Object.assign(subject,methods,{
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},
    clients:[client],selectedAssetsClientId:'c1',externalAssetType:'GOOGLE',externalAssetForm,showExternalAssetModal:true,
    mediaTools:[tool],toolForm,showToolModal:true,toolPasswordVisible:{t1:true},
    reminderTypes:[reminder],reminderTypeForm,newAlertForm:{typeKey:kind==='reminder-delete'?'CUSTOM_1':'IP'},alertTypeFilter:kind==='reminder-delete'?'CUSTOM_1':'ALL',
    leads:[],openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[{id:'audit-existing',action:'EXISTING'}],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    canManageAssets:()=>true,canManageReminderTypes:()=>true,reminderTypeUsageCount:()=>0,
    defaultExternalAssetForm:()=>({id:null,accountName:'',loginAccount:'',note:''}),normalizeMediaTool:value=>({...value}),accountUid:type=>type==='google'?'g-created':type==='tool'?'t-created':`${type}-created`,
    askConfirm:(config,action)=>{subject.__confirm={config,action}},
    resetReminderTypeForm:()=>{resetCount+=1;subject.reminderTypeForm={key:'',name:''}},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:clone(subject.clients),mediaTools:clone(subject.mediaTools),reminderTypes:clone(subject.reminderTypes),leads:[],openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,asset,client,tool,reminder,resolveFirst:status=>gate?.resolve(response(status)),getResetCount:()=>resetCount};
}
function invoke(kind,subject){
  if(kind==='external-save')return subject.saveExternalAsset();
  if(kind==='external-delete'){subject.deleteExternalAsset('GOOGLE',subject.clients[0].googleAccounts[0]);return confirm(subject)}
  if(kind==='media-save')return subject.saveMediaTool();
  if(kind==='media-delete'){subject.deleteMediaTool(subject.mediaTools[0]);return confirm(subject)}
  if(kind==='reminder-save')return subject.saveReminderType();
  if(kind==='reminder-delete'){subject.deleteReminderType(subject.reminderTypes[0]);return confirm(subject)}
  fail('unknown kind '+kind);
}
function confirm(subject){if(typeof subject.__confirm?.action!=='function')fail('confirmation callback missing');return subject.__confirm.action()}
async function waitFirstSave(calls){for(let i=0;i<40&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending resource save before ACK')}
async function waitRollback(calls){for(let i=0;i<40&&calls.fetch.length<2;i+=1)await sleep(10);ok(calls.fetch.length>=2,'failed resource mutation must persist rollback truth');return parseState(calls.fetch.at(-1))}
async function laterPersist(subject,calls){subject.persist();await sleep(240);return parseState(calls.fetch.at(-1))}
const successNotice=(kind,calls)=>calls.notify.some(m=>kind.includes('delete')?/已删除/.test(m):/已保存|已添加|已修改/.test(m));

// Every interactive resource mutation serializes its tentative state first and holds
// completion UI until the exact state receives cloud ACK.
for(const kind of ['external-save','external-delete','media-save','media-delete','reminder-save','reminder-delete']){
  const {subject,calls,resolveFirst,getResetCount}=makeRuntime({kind,mode:'create',first:'deferred'});
  const task=invoke(kind,subject);ok(task&&typeof task.then==='function',`${kind} exposes ACK promise`);await waitFirstSave(calls);
  eq(successNotice(kind,calls),false,`${kind} success notice held before ACK`);
  const pending=parseState(calls.fetch[0]);
  if(kind==='external-save'){ok(byId(pending.clients?.[0]?.googleAccounts,'g-created'),'external create serialized');eq(subject.showExternalAssetModal,true,'external modal held before ACK')}
  if(kind==='external-delete')eq(byId(pending.clients?.[0]?.googleAccounts,'g1'),undefined,'external delete serialized');
  if(kind==='media-save'){ok(byId(pending.mediaTools,'t-created'),'media create serialized');eq(subject.showToolModal,true,'media modal held before ACK')}
  if(kind==='media-delete')eq(byId(pending.mediaTools,'t1'),undefined,'media delete serialized');
  if(kind==='reminder-save'){ok((pending.reminderTypes||[]).some(t=>String(t.key).startsWith('CUSTOM_')&&t.name==='Reminder Created'),'reminder create serialized');eq(subject.newAlertForm.typeKey,'IP','reminder create UI selection held before ACK');eq(getResetCount(),0,'reminder form reset held before ACK')}
  if(kind==='reminder-delete'){eq(byKey(pending.reminderTypes,'CUSTOM_1'),undefined,'reminder delete serialized');eq(subject.newAlertForm.typeKey,'CUSTOM_1','reminder delete new-alert selection held before ACK');eq(subject.alertTypeFilter,'CUSTOM_1','reminder delete filter held before ACK')}
  resolveFirst(200);await task;eq(calls.fetch.length,1,`${kind} success uses one durable save`);ok(successNotice(kind,calls),`${kind} success notice emitted after ACK`);
  if(kind==='external-save')eq(subject.showExternalAssetModal,false,'external modal closes after ACK');
  if(kind==='media-save')eq(subject.showToolModal,false,'media modal closes after ACK');
  if(kind==='reminder-save'){ok(String(subject.newAlertForm.typeKey).startsWith('CUSTOM_'),'reminder create selection commits after ACK');eq(getResetCount(),1,'reminder form resets after ACK')}
  if(kind==='reminder-delete'){eq(subject.newAlertForm.typeKey,'IP','reminder delete selection commits after ACK');eq(subject.alertTypeFilter,'ALL','reminder delete filter commits after ACK')}
}

// Failed ACK restores each operation's owned business state and audit, persists the
// rollback truth, and later ordinary persistence cannot resurrect the failed change.
for(const kind of ['external-save','external-delete','media-save','media-delete','reminder-save','reminder-delete']){
  const mode=kind.includes('save')?'edit':'create';
  const {subject,calls,getResetCount}=makeRuntime({kind,mode,first:'fail'});
  const before={clients:clone(subject.clients),mediaTools:clone(subject.mediaTools),reminderTypes:clone(subject.reminderTypes),newType:subject.newAlertForm.typeKey,filter:subject.alertTypeFilter};
  await invoke(kind,subject);
  same(subject.clients,before.clients,`${kind} failed ACK restores clients`);same(subject.mediaTools,before.mediaTools,`${kind} failed ACK restores tools`);same(subject.reminderTypes,before.reminderTypes,`${kind} failed ACK restores reminder types`);
  eq(subject.auditLogs.length,1,`${kind} failed ACK removes only attempt audit`);ok(calls.notify.some(m=>/云端保存失败/.test(m)),`${kind} failure notice`);
  if(kind==='reminder-save')eq(getResetCount(),0,'failed reminder save does not reset form');
  if(kind==='reminder-delete'){eq(subject.newAlertForm.typeKey,before.newType,'failed reminder delete preserves new-alert selection');eq(subject.alertTypeFilter,before.filter,'failed reminder delete preserves filter')}
  const rollback=await waitRollback(calls);same(rollback.clients,before.clients,`${kind} rollback cloud clients`);same(rollback.mediaTools,before.mediaTools,`${kind} rollback cloud tools`);same(rollback.reminderTypes,before.reminderTypes,`${kind} rollback cloud reminder types`);eq((rollback.auditLogs||[]).length,1,`${kind} rollback cloud audit`);
  const later=await laterPersist(subject,calls);same(later.clients,before.clients,`${kind} later persist cannot resurrect client mutation`);same(later.mediaTools,before.mediaTools,`${kind} later persist cannot resurrect tool mutation`);same(later.reminderTypes,before.reminderTypes,`${kind} later persist cannot resurrect reminder mutation`);
}

// Newer same-ID resource authority wins over stale rollback.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'external-save',mode:'edit',first:'deferred'});const task=invoke('external-save',subject);await waitFirstSave(calls);
  const replacement={id:'g1',accountName:'Concurrent Google',loginAccount:'concurrent',note:'newer'};subject.clients[0].googleAccounts.splice(0,1,replacement);resolveFirst(503);await task;eq(subject.clients[0].googleAccounts[0],replacement,'external same-ID replacement preserved');const rollback=await waitRollback(calls);eq(byId(rollback.clients?.[0]?.googleAccounts,'g1')?.accountName,'Concurrent Google','external replacement reaches rollback cloud truth');
}
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'media-delete',first:'deferred'});const task=invoke('media-delete',subject);await waitFirstSave(calls);
  const replacement={id:'t1',name:'Concurrent Tool',bindings:['c1'],seats:5};subject.mediaTools.push(replacement);resolveFirst(503);await task;eq(byId(subject.mediaTools,'t1'),replacement,'media same-ID replacement preserved');const rollback=await waitRollback(calls);eq(byId(rollback.mediaTools,'t1')?.name,'Concurrent Tool','media replacement reaches rollback cloud truth');
}
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'reminder-save',mode:'edit',first:'deferred'});const task=invoke('reminder-save',subject);await waitFirstSave(calls);
  subject.reminderTypes[0].name='Concurrent Reminder';resolveFirst(503);await task;eq(subject.reminderTypes[0].name,'Concurrent Reminder','reminder concurrent field edit preserved');const rollback=await waitRollback(calls);eq(byKey(rollback.reminderTypes,'CUSTOM_1')?.name,'Concurrent Reminder','reminder concurrent edit reaches rollback cloud truth');
}

// Missing durability service fails closed before any business mutation, audit, modal
// completion, confirmation-side delete, or network request.
for(const kind of ['external-save','external-delete','media-save','media-delete','reminder-save','reminder-delete']){
  const mode=kind.includes('save')?'edit':'create',runtime=makeRuntime({kind,mode,first:'deferred',withBarrier:false}),{subject,calls}=runtime;
  const before={clients:clone(subject.clients),mediaTools:clone(subject.mediaTools),reminderTypes:clone(subject.reminderTypes),audits:clone(subject.auditLogs),externalModal:subject.showExternalAssetModal,toolModal:subject.showToolModal,newType:subject.newAlertForm.typeKey,filter:subject.alertTypeFilter};
  const result=invoke(kind,subject);eq(result,undefined,`${kind} missing barrier returns synchronously`);eq(calls.fetch.length,0,`${kind} missing barrier sends zero network saves`);same(subject.clients,before.clients,`${kind} missing barrier preserves clients`);same(subject.mediaTools,before.mediaTools,`${kind} missing barrier preserves media tools`);same(subject.reminderTypes,before.reminderTypes,`${kind} missing barrier preserves reminder types`);same(subject.auditLogs,before.audits,`${kind} missing barrier preserves audits`);eq(subject.showExternalAssetModal,before.externalModal,`${kind} missing barrier preserves external modal`);eq(subject.showToolModal,before.toolModal,`${kind} missing barrier preserves tool modal`);eq(subject.newAlertForm.typeKey,before.newType,`${kind} missing barrier preserves reminder selection`);eq(subject.alertTypeFilter,before.filter,`${kind} missing barrier preserves filter`);ok(calls.notify.some(m=>/持久化服务不可用/.test(m)),`${kind} missing barrier explains fail-closed state`);
}

console.log('BUSINESS_RESOURCE_CATALOG_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; external-asset+media-tool+reminder-type save/delete=success-after-single-save-ACK; failure=operation-state+attempt-audit-rollback+rollback-persisted; later-persist=failed-operation-not-resurrected; concurrency=same-id+field-level-authority-preserved; UI modal+reminder-selection/reset=ACK-gated; missing-barrier=fail-closed');
