import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of [
  'vm.createBackupSnapshot=',
  'vm.deleteBackupSnapshot=',
  'vm.restoreBackupSnapshot=',
  'vm.downloadFullBackup=',
  'vm.importFullBackup=',
  'function sanitizedBackupPayload()',
  'function applyBusinessBackup(',
]){
  if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: authoritative adapter marker missing: ${marker}`);
}

function equal(actual,expected,label){
  if(actual!==expected)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);
}
function truthy(value,label){if(!value)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}`);}

function makeRuntime({role='ADMIN',confirm=true,backupSnapshots=[],payload=null}={}){
  const calls={fetch:0,persist:0,storage:0,audit:[],notify:[],confirm:[],click:0,remove:0,revoke:[],objectUrls:[],fileReads:0};
  const basePayload=payload??{
    clients:[{id:'client-old',name:'Old Client'}],
    standaloneAlerts:[{id:'alert-old'}],
    reminderTypes:[{key:'CUSTOM',label:'Custom'}],
    dismissedAlerts:['dismissed-old'],
    leads:[{id:'lead-old'}],
    openingProviders:[{id:'provider-old'}],
    openingDeals:[{id:'deal-old'}],
    financeActualRebates:[{id:'rebate-old'}],
    financeReceivables:[{id:'receivable-old'}],
    financeCosts:[{id:'cost-old'}],
    financeReconciliations:[{id:'reconciliation-old'}],
    financeMonthLocks:{'2026-09':true},
    financeMonthSnapshots:{'2026-09':{locked:true}},
    sopProgress:{'step-old':true},
    mediaTools:[{id:'tool-old'}],
    auditLogs:[{id:'audit-old'}],
    authUsers:[{id:'secret-user',password:'must-not-export'}],
    backupSnapshots:[{id:'nested-backup',payload:{secret:true}}],
  };
  let confirmPromise=Promise.resolve();
  let capturedBlob=null;
  const subject={};

  const storage=new Map();
  const localStorage={
    getItem:key=>storage.get(key)??null,
    setItem:(key,value)=>storage.set(key,String(value)),
    removeItem:key=>storage.delete(key),
  };
  const document={
    body:{appendChild:()=>{}},
    createElement(tag){
      if(tag!=='a')throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: unexpected element ${tag}`);
      return {href:'',download:'',click(){calls.click+=1;},remove(){calls.remove+=1;}};
    },
  };
  const URLMock={
    createObjectURL(blob){capturedBlob=blob;const url='blob:synthetic-backup';calls.objectUrls.push(url);return url;},
    revokeObjectURL(url){calls.revoke.push(url);},
  };
  class FileReaderMock{
    result='';
    onload=null;
    readAsText(file){calls.fileReads+=1;this.result=String(file?.contents??'');this.onload?.();}
  }
  const window={__growthOpsVm:subject,__GROWTHOPS_SUPABASE_URL__:'',__GROWTHOPS_SUPABASE_KEY__:'',location:{hash:'#system'}};
  const context={
    window,document,localStorage,URL:URLMock,FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,
    console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,
    fetch:async()=>{calls.fetch+=1;throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: unexpected real/network fetch');},
  };
  // Load the final shipped adapter first. It initializes cloud-managed state on mount,
  // so synthetic business state must be injected only after this authoritative code runs.
  vm.runInNewContext(adapter,context,{timeout:1000});

  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role,enabled:true},
    currentPage:'system',
    backupSnapshots:backupSnapshots.map(item=>structuredClone(item)),
    clients:[{id:'client-before',name:'Before Client'}],
    standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],
    financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},
    sopProgress:{},auditLogs:[],mediaTools:[],authUsers:[{id:'admin-current'}],
    defaultReminderTypes:()=>[{key:'RENEWAL',label:'Renewal'}],
    collectBackupPayload:()=>structuredClone(basePayload),
    normalizeClient:value=>({...value,normalizedClient:true}),
    normalizeStandaloneAlert:value=>({...value,normalizedAlert:true}),
    normalizeReminderTypes:value=>structuredClone(value),
    normalizeOpeningProvider:value=>({...value,normalizedProvider:true}),
    normalizeFinanceActualRebates:value=>structuredClone(value),
    normalizeReceivable:value=>({...value,normalizedReceivable:true}),
    normalizeFinanceCost:value=>({...value,normalizedCost:true}),
    normalizeMediaTool:value=>({...value,normalizedTool:true}),
    migrateLegacyAccountSpendRecords:()=>{},
    migrateLegacyActualRebatesToReconciliations:()=>{},
    ensureAutomaticReceivables:()=>{},
    ensureAutomaticAssetCosts:()=>{},
    ensureAutomaticOpeningFeeCosts:()=>{},
    ensureReceivableLinkedCosts:()=>{},
    ensureFinanceSnapshotsForLocks:()=>{},
    syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},
    canViewPage:()=>true,
    localDateKey:()=> '2026-09-01',
    roleLabel:value=>String(value||''),
    logAudit:(...args)=>calls.audit.push(args),
    notify:message=>calls.notify.push(String(message)),
    updateStorageUsage:()=>{calls.storage+=1;},
    persist:()=>{calls.persist+=1;return true;},
    askConfirm:(config,callback)=>{
      calls.confirm.push(config);
      if(confirm)confirmPromise=Promise.resolve().then(callback);
    },
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(client=>!client.archived);}});
  return {subject,calls,waitConfirm:()=>confirmPromise,getCapturedBlob:()=>capturedBlob};
}

// Snapshot creation must export only sanitized business state, retain at most five snapshots,
// persist immediately, and only create audit/notice side effects when explicitly requested.
{
  const old=Array.from({length:5},(_,index)=>({id:`old-${index}`,name:`Old ${index}`,payload:{clients:[]}}));
  const {subject,calls}=makeRuntime({backupSnapshots:old});
  const snap=subject.createBackupSnapshot(false);
  equal(subject.backupSnapshots.length,5,'snapshot retention cap');
  truthy(subject.backupSnapshots[0]===snap,'new snapshot must be first');
  truthy(!old.some(item=>item.id===snap.id),'new snapshot id must not collide with retained history');
  equal(snap.backupDate,'2026-09-01','snapshot backupDate');
  equal(snap.payload.version,'growth-ops-cloud-backup-v2','snapshot payload version');
  truthy(!('authUsers' in snap.payload),'snapshot must exclude authUsers');
  truthy(!('backupSnapshots' in snap.payload),'snapshot must exclude nested backups');
  equal(calls.persist,1,'silent snapshot persist count');
  equal(calls.storage,1,'silent snapshot storage refresh count');
  equal(calls.audit.length,0,'silent snapshot audit count');
  equal(calls.notify.length,0,'silent snapshot notice count');
  equal(calls.fetch,0,'snapshot creation must not directly call network');
}
{
  const {subject,calls}=makeRuntime();
  subject.createBackupSnapshot(true);
  equal(calls.persist,2,'notified snapshot persist phases');
  equal(calls.audit.length,1,'notified snapshot audit count');
  equal(calls.audit[0][0],'创建数据快照','notified snapshot audit action');
  equal(calls.notify.at(-1),'已创建云端数据快照','notified snapshot success notice');
}

// Snapshot deletion: admin-only, confirmation-gated, id-scoped, and success effects occur once.
{
  const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[{id:'snap-a',name:'A'}]});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  equal(subject.backupSnapshots.length,1,'non-admin delete must preserve snapshots');
  equal(calls.confirm.length,0,'non-admin delete must not confirm');
  equal(calls.persist,0,'non-admin delete must not persist');
  truthy(calls.notify.at(-1).includes('只有管理员'),'non-admin delete notice');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[{id:'snap-a',name:'A'}]});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  await waitConfirm();
  equal(calls.confirm.length,1,'cancel delete confirm count');
  equal(subject.backupSnapshots.length,1,'cancel delete must preserve snapshot');
  equal(calls.persist,0,'cancel delete persist count');
  equal(calls.audit.length,0,'cancel delete audit count');
}
{
  const snapshots=[{id:'snap-a',name:'A'},{id:'snap-b',name:'B'}];
  const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:snapshots});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  await waitConfirm();
  equal(subject.backupSnapshots.length,1,'confirmed delete resulting length');
  equal(subject.backupSnapshots[0].id,'snap-b','confirmed delete must be id-scoped');
  equal(calls.persist,1,'confirmed delete persist count');
  equal(calls.audit.length,1,'confirmed delete audit count');
  equal(calls.notify.at(-1),'云端快照已删除','confirmed delete notice');
}

// Restore must protect the current state first, then replace business state from the selected
// snapshot without importing authUsers, and remain confirmation/admin gated.
const restorePayload={
  clients:[{id:'client-restored',name:'Restored Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],
  openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],
  financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{restored:true},mediaTools:[],auditLogs:[{id:'audit-restored'}],
  authUsers:[{id:'attacker-user'}],backupSnapshots:[{id:'nested-attacker'}],
};
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};
  const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[snap]});
  subject.restoreBackupSnapshot(snap);
  equal(subject.clients[0].id,'client-before','non-admin restore must preserve current business state');
  equal(calls.confirm.length,0,'non-admin restore must not confirm');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[snap]});
  subject.restoreBackupSnapshot(snap);
  await waitConfirm();
  equal(subject.clients[0].id,'client-before','cancelled restore must preserve current business state');
  equal(calls.persist,0,'cancelled restore persist count');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};
  const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:[snap]});
  subject.restoreBackupSnapshot(snap);
  await waitConfirm();
  equal(subject.clients[0].id,'client-restored','confirmed restore client state');
  equal(subject.clients[0].normalizedClient,true,'confirmed restore must use shipped normalizer');
  equal(subject.authUsers[0].id,'admin-current','restore must not import authUsers from business snapshot');
  truthy(subject.backupSnapshots.length>=2,'restore must create a protection snapshot before applying payload');
  truthy(subject.backupSnapshots.some(item=>item.id!=='restore-a'),'restore protection snapshot must be distinct from selected snapshot');
  equal(subject.sopProgress.restored,true,'restore must apply SOP progress');
  equal(calls.audit.at(-1)[0],'恢复数据快照','restore audit action');
  equal(calls.notify.at(-1),'数据快照已恢复并同步云端','restore success notice');
  equal(calls.fetch,0,'restore must not directly call network');
  truthy(calls.persist>=3,'restore must persist protection, applied state, and success audit phases');
}

// Full export must be sanitized and trigger exactly one download lifecycle without network.
{
  const {subject,calls,getCapturedBlob}=makeRuntime();
  subject.downloadFullBackup();
  equal(calls.click,1,'backup export click count');
  equal(calls.remove,1,'backup export anchor cleanup count');
  equal(calls.revoke.length,1,'backup export object URL revoke count');
  const blob=getCapturedBlob();
  truthy(blob instanceof Blob,'backup export must create a Blob');
  const exported=JSON.parse(await blob.text());
  equal(exported.version,'growth-ops-cloud-backup-v2','export payload version');
  truthy(!('authUsers' in exported),'full export must exclude authUsers');
  truthy(!('backupSnapshots' in exported),'full export must exclude backupSnapshots');
  equal(calls.audit.length,1,'backup export audit count');
  equal(calls.persist,1,'backup export persist count');
  equal(calls.notify.at(-1),'业务数据备份已导出','backup export success notice');
  equal(calls.fetch,0,'backup export must not call network');
}

// Import must be admin-only, clear the file input, validate JSON/business shape before confirmation,
// create a protection snapshot, apply the payload, and keep server auth users out of imported data.
{
  const {subject,calls}=makeRuntime({role:'OPS'});
  const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};
  subject.importFullBackup(event);
  equal(event.target.value,'','non-admin import must clear file input');
  equal(calls.fileReads,0,'non-admin import must not read file');
  equal(calls.confirm.length,0,'non-admin import must not confirm');
}
{
  const {subject,calls}=makeRuntime();
  const event={target:{files:[{name:'bad.json',contents:'{"notClients":true}'}],value:'selected'}};
  subject.importFullBackup(event);
  equal(calls.fileReads,1,'invalid import read count');
  equal(calls.confirm.length,0,'invalid import must fail before confirmation');
  equal(calls.persist,0,'invalid import must not persist');
  truthy(calls.notify.at(-1).includes('无效备份文件'),'invalid import notice');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false});
  const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};
  subject.importFullBackup(event);
  await waitConfirm();
  equal(event.target.value,'','cancelled import must clear file input');
  equal(calls.confirm.length,1,'cancelled import confirmation count');
  equal(subject.clients[0].id,'client-before','cancelled import must preserve business state');
  equal(calls.persist,0,'cancelled import persist count');
}
{
  const {subject,calls,waitConfirm}=makeRuntime();
  const event={target:{files:[{name:'backup.json',contents:JSON.stringify(restorePayload)}],value:'selected'}};
  subject.importFullBackup(event);
  await waitConfirm();
  equal(subject.clients[0].id,'client-restored','confirmed import client state');
  equal(subject.authUsers[0].id,'admin-current','confirmed import must not overwrite auth users');
  truthy(subject.backupSnapshots.length>=1,'confirmed import must create protection snapshot');
  equal(calls.audit.at(-1)[0],'导入全量备份','confirmed import audit action');
  equal(calls.audit.at(-1)[1],'backup.json','confirmed import audit filename');
  equal(calls.notify.at(-1),'备份已导入并同步云端','confirmed import success notice');
  equal(calls.fetch,0,'confirmed import must not directly call network');
}

console.log('BUSINESS_BACKUP_MUTATIONS_OK: authority=final-cloud-adapter; snapshot=sanitize+cap+persist; delete=admin+confirm+id-scope; restore=protect+apply+auth-isolated; export=sanitized+download; import=admin+parse+confirm+protect+auth-isolated; network=zero');
