import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['vm.createBackupSnapshot=','vm.deleteBackupSnapshot=','vm.restoreBackupSnapshot=','vm.downloadFullBackup=','vm.importFullBackup=','function sanitizedBackupPayload()','function applyBusinessBackup(']){
  if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: authoritative adapter marker missing: ${marker}`);
}

function eq(actual,expected,label){if(actual!==expected)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);}
function ok(value,label){if(!value)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}`);}

function makeRuntime({role='ADMIN',confirm=true,backupSnapshots=[],payload=null}={}){
  const calls={fetch:0,persist:0,storage:0,audit:[],notify:[],confirm:[],click:0,remove:0,revoke:[],fileReads:0};
  const basePayload=payload??{
    clients:[{id:'client-old',name:'Old Client'}],standaloneAlerts:[{id:'alert-old'}],reminderTypes:[{key:'CUSTOM',label:'Custom'}],dismissedAlerts:['dismissed-old'],
    leads:[{id:'lead-old'}],openingProviders:[{id:'provider-old'}],openingDeals:[{id:'deal-old'}],financeActualRebates:[{id:'rebate-old'}],
    financeReceivables:[{id:'receivable-old'}],financeCosts:[{id:'cost-old'}],financeReconciliations:[{id:'reconciliation-old'}],
    financeMonthLocks:{'2026-09':true},financeMonthSnapshots:{'2026-09':{locked:true}},sopProgress:{'step-old':true},mediaTools:[{id:'tool-old'}],auditLogs:[{id:'audit-old'}],
    authUsers:[{id:'secret-user',password:'must-not-export'}],backupSnapshots:[{id:'nested-backup',payload:{secret:true}}],
  };
  let confirmPromise=Promise.resolve();
  let capturedBlob=null;
  let uidCounter=0;
  const subject={};
  const storage=new Map();
  const localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
  const document={body:{appendChild:()=>{}},createElement(tag){if(tag!=='a')throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: unexpected element ${tag}`);return {href:'',download:'',click(){calls.click+=1;},remove(){calls.remove+=1;}};}};
  const URLMock={createObjectURL(blob){capturedBlob=blob;return 'blob:synthetic-backup';},revokeObjectURL(url){calls.revoke.push(url);}};
  class FileReaderMock{result='';onload=null;readAsText(file){calls.fileReads+=1;this.result=String(file?.contents??'');this.onload?.();}}
  const window={__growthOpsVm:subject,__GROWTHOPS_SUPABASE_URL__:'',__GROWTHOPS_SUPABASE_KEY__:'',location:{hash:'#system'}};
  const context={window,document,localStorage,URL:URLMock,FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,
    fetch:async()=>{calls.fetch+=1;throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: unexpected real/network fetch');}};
  vm.runInNewContext(adapter,context,{timeout:1000});

  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role,enabled:true},currentPage:'system',backupSnapshots:backupSnapshots.map(item=>structuredClone(item)),
    clients:[{id:'client-before',name:'Before Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],
    financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{},auditLogs:[],mediaTools:[],authUsers:[{id:'admin-current'}],
    accountUid:prefix=>`${prefix}-test-${++uidCounter}`,
    defaultReminderTypes:()=>[{key:'RENEWAL',label:'Renewal'}],collectBackupPayload:()=>structuredClone(basePayload),
    normalizeClient:value=>({...value,normalizedClient:true}),normalizeStandaloneAlert:value=>({...value,normalizedAlert:true}),normalizeReminderTypes:value=>structuredClone(value),
    normalizeOpeningProvider:value=>({...value,normalizedProvider:true}),normalizeFinanceActualRebates:value=>structuredClone(value),normalizeReceivable:value=>({...value,normalizedReceivable:true}),
    normalizeFinanceCost:value=>({...value,normalizedCost:true}),normalizeMediaTool:value=>({...value,normalizedTool:true}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},
    ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},
    restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},
    syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,localDateKey:()=> '2026-09-01',roleLabel:value=>String(value||''),
    logAudit:(...args)=>calls.audit.push(args),notify:message=>calls.notify.push(String(message)),updateStorageUsage:()=>{calls.storage+=1;},persist:()=>{calls.persist+=1;return true;},
    askConfirm:(config,callback)=>{calls.confirm.push(config);if(confirm)confirmPromise=Promise.resolve().then(callback);},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(client=>!client.archived);}});
  return {subject,calls,waitConfirm:()=>confirmPromise,getCapturedBlob:()=>capturedBlob};
}

// Create: sanitize sensitive/server-managed state, cap history, and preserve success phases.
{
  const old=Array.from({length:5},(_,index)=>({id:`old-${index}`,name:`Old ${index}`,payload:{clients:[]}}));
  const {subject,calls}=makeRuntime({backupSnapshots:old});
  const snap=subject.createBackupSnapshot(false);
  eq(subject.backupSnapshots.length,5,'snapshot retention cap');ok(subject.backupSnapshots[0]===snap,'new snapshot must be first');
  eq(snap.backupDate,'2026-09-01','snapshot backupDate');eq(snap.payload.version,'growth-ops-cloud-backup-v2','snapshot payload version');
  ok(!('authUsers' in snap.payload),'snapshot excludes authUsers');ok(!('backupSnapshots' in snap.payload),'snapshot excludes nested backups');
  eq(calls.persist,1,'silent snapshot persist');eq(calls.storage,1,'silent snapshot storage refresh');eq(calls.audit.length,0,'silent snapshot audit');eq(calls.notify.length,0,'silent snapshot notice');eq(calls.fetch,0,'snapshot network');
}
{
  const {subject,calls}=makeRuntime();subject.createBackupSnapshot(true);
  eq(calls.persist,2,'notified snapshot persist phases');eq(calls.audit.length,1,'notified snapshot audit');eq(calls.audit[0][0],'创建数据快照','snapshot audit action');eq(calls.notify.at(-1),'已创建云端数据快照','snapshot notice');
}

// Delete: admin + confirmation + exact id scope.
{
  const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[{id:'snap-a',name:'A'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  eq(subject.backupSnapshots.length,1,'non-admin delete state');eq(calls.confirm.length,0,'non-admin delete confirm');eq(calls.persist,0,'non-admin delete persist');ok(calls.notify.at(-1).includes('只有管理员'),'non-admin delete notice');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[{id:'snap-a',name:'A'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);await waitConfirm();
  eq(subject.backupSnapshots.length,1,'cancel delete state');eq(calls.persist,0,'cancel delete persist');eq(calls.audit.length,0,'cancel delete audit');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:[{id:'snap-a',name:'A'},{id:'snap-b',name:'B'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);await waitConfirm();
  eq(subject.backupSnapshots.length,1,'confirmed delete length');eq(subject.backupSnapshots[0].id,'snap-b','confirmed delete scope');eq(calls.persist,1,'confirmed delete persist');eq(calls.audit.length,1,'confirmed delete audit');
}

const restorePayload={clients:[{id:'client-restored',name:'Restored Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],
  financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{restored:true},mediaTools:[],auditLogs:[{id:'audit-restored'}],
  authUsers:[{id:'attacker-user'}],backupSnapshots:[{id:'nested-attacker'}]};

// Restore: protect current state first, apply business state, never import auth users.
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);
  eq(subject.clients[0].id,'client-before','non-admin restore state');eq(calls.confirm.length,0,'non-admin restore confirm');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);await waitConfirm();
  eq(subject.clients[0].id,'client-before','cancel restore state');eq(calls.persist,0,'cancel restore persist');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);await waitConfirm();
  eq(subject.clients[0].id,'client-restored','restore client');eq(subject.clients[0].normalizedClient,true,'restore normalizer');eq(subject.authUsers[0].id,'admin-current','restore auth isolation');
  ok(subject.backupSnapshots.length>=2,'restore protection snapshot');eq(subject.sopProgress.restored,true,'restore SOP');eq(calls.audit.at(-1)[0],'恢复数据快照','restore audit');eq(calls.notify.at(-1),'数据快照已恢复并同步云端','restore notice');
  ok(calls.persist>=3,'restore persist phases');eq(calls.fetch,0,'restore network');
}

// Export: sanitized payload and one browser download lifecycle.
{
  const {subject,calls,getCapturedBlob}=makeRuntime();subject.downloadFullBackup();
  eq(calls.click,1,'export click');eq(calls.remove,1,'export cleanup');eq(calls.revoke.length,1,'export revoke');
  const exported=JSON.parse(await getCapturedBlob().text());eq(exported.version,'growth-ops-cloud-backup-v2','export version');ok(!('authUsers' in exported),'export auth isolation');ok(!('backupSnapshots' in exported),'export nested-backup isolation');
  eq(calls.audit.length,1,'export audit');eq(calls.persist,1,'export persist');eq(calls.notify.at(-1),'业务数据备份已导出','export notice');eq(calls.fetch,0,'export network');
}

// Import: admin + parse + confirmation + protection snapshot + auth isolation.
{
  const {subject,calls}=makeRuntime({role:'OPS'});const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};subject.importFullBackup(event);
  eq(event.target.value,'','non-admin import clears file');eq(calls.fileReads,0,'non-admin import read');eq(calls.confirm.length,0,'non-admin import confirm');
}
{
  const {subject,calls}=makeRuntime();const event={target:{files:[{name:'bad.json',contents:'{"notClients":true}'}],value:'selected'}};subject.importFullBackup(event);
  eq(calls.fileReads,1,'invalid import read');eq(calls.confirm.length,0,'invalid import confirm');eq(calls.persist,0,'invalid import persist');ok(calls.notify.at(-1).includes('无效备份文件'),'invalid import notice');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false});const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};subject.importFullBackup(event);await waitConfirm();
  eq(event.target.value,'','cancel import clears file');eq(calls.confirm.length,1,'cancel import confirm');eq(subject.clients[0].id,'client-before','cancel import state');eq(calls.persist,0,'cancel import persist');
}
{
  const {subject,calls,waitConfirm}=makeRuntime();const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};subject.importFullBackup(event);await waitConfirm();
  eq(subject.clients[0].id,'client-restored','import client');eq(subject.authUsers[0].id,'admin-current','import auth isolation');ok(subject.backupSnapshots.length>=1,'import protection snapshot');
  eq(calls.audit.at(-1)[0],'导入全量备份','import audit');eq(calls.audit.at(-1)[1],'backup.json','import audit filename');eq(calls.notify.at(-1),'备份已导入并同步云端','import notice');eq(calls.fetch,0,'import network');
}

console.log('BUSINESS_BACKUP_MUTATIONS_OK: authority=final-cloud-adapter; snapshot=sanitize+cap+persist; delete=admin+confirm+id-scope; restore=protect+apply+auth-isolated; export=sanitized+download; import=admin+parse+confirm+protect+auth-isolated; network=zero');
