import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['vm.createBackupSnapshot=','vm.deleteBackupSnapshot=','vm.restoreBackupSnapshot=','vm.downloadFullBackup=','vm.importFullBackup=','function sanitizedBackupPayload()','function applyBusinessBackup(','growth-ops-cloud-backup-v4-redacted','redactBackupSecrets','async function flushSave()']){
  if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: authoritative adapter marker missing: ${marker}`);
}
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_BACKUP_MUTATIONS_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Synthetic mutation harness: do not start cloud/session boot.\n})();');
const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const ok=(value,label)=>{if(!value)throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: ${label}`);};

function makeRuntime({role='ADMIN',confirm=true,backupSnapshots=[],payload=null}={}){
  const calls={fetch:0,persist:0,storage:0,audit:[],notify:[],confirm:[],click:0,remove:0,revoke:[],fileReads:0};
  const basePayload=payload??{
    clients:[{id:'client-old',name:'Old Client',loginAccount:'old@example.test',password:'must-not-export',nested:{twoFactor:'secret-2fa'}}],
    standaloneAlerts:[{id:'alert-old'}],reminderTypes:[{key:'CUSTOM',label:'Custom'}],dismissedAlerts:['dismissed-old'],leads:[{id:'lead-old'}],
    openingProviders:[{id:'provider-old'}],openingDeals:[{id:'deal-old'}],financeActualRebates:[{id:'rebate-old'}],financeReceivables:[{id:'receivable-old'}],financeCosts:[{id:'cost-old'}],
    financeReconciliations:[{id:'reconciliation-old'}],financeMonthLocks:{'2026-09':true},financeMonthSnapshots:{'2026-09':{locked:true}},sopProgress:{'step-old':true},mediaTools:[{id:'tool-old'}],
    auditLogs:[{id:'audit-old'}],authUsers:[{id:'secret-user',password:'must-not-export-user'}],backupSnapshots:[{id:'nested-backup',payload:{secret:true}}],
  };
  let confirmPromise=Promise.resolve(),capturedBlob=null,uidCounter=0;
  const subject={},storage=new Map();
  const localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement(tag){if(tag!=='a')throw new Error(`BUSINESS_BACKUP_MUTATIONS_FAILED: unexpected element ${tag}`);return {href:'',download:'',click(){calls.click+=1;},remove(){calls.remove+=1;}};}};
  const URLMock={createObjectURL(blob){capturedBlob=blob;return 'blob:synthetic-backup';},revokeObjectURL(url){calls.revoke.push(url);}};
  class FileReaderMock{result='';onload=null;readAsText(file){calls.fileReads+=1;this.result=String(file?.contents??'');this.onload?.();}}
  const window={__growthOpsVm:subject,__GROWTHOPS_SUPABASE_URL__:'',__GROWTHOPS_SUPABASE_KEY__:'',location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:URLMock,FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,
    fetch:async()=>{calls.fetch+=1;return {ok:true,status:200,json:async()=>({revision:calls.fetch})};}},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role,enabled:true},currentPage:'system',backupSnapshots:backupSnapshots.map(item=>structuredClone(item)),clients:[{id:'client-before',name:'Before Client'}],
    standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],
    financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{},auditLogs:[],mediaTools:[],authUsers:[{id:'admin-current'}],accountUid:prefix=>`${prefix}-test-${++uidCounter}`,
    defaultReminderTypes:()=>[{key:'RENEWAL',label:'Renewal'}],collectBackupPayload:()=>structuredClone(basePayload),normalizeClient:value=>({...value,normalizedClient:true}),
    normalizeStandaloneAlert:value=>({...value,normalizedAlert:true}),normalizeReminderTypes:value=>structuredClone(value),normalizeOpeningProvider:value=>({...value,normalizedProvider:true}),
    normalizeFinanceActualRebates:value=>structuredClone(value),normalizeReceivable:value=>({...value,normalizedReceivable:true}),normalizeFinanceCost:value=>({...value,normalizedCost:true}),normalizeMediaTool:value=>({...value,normalizedTool:true}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureDailyBackup:()=>{},
    ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},
    syncSopAccountSelection:()=>{},canViewPage:()=>true,localDateKey:()=> '2026-09-01',roleLabel:value=>String(value||''),logAudit:(...args)=>calls.audit.push(args),notify:message=>calls.notify.push(String(message)),
    updateStorageUsage:()=>{calls.storage+=1;},persist:()=>{calls.persist+=1;return true;},askConfirm:(config,callback)=>{calls.confirm.push(config);if(confirm)confirmPromise=Promise.resolve().then(callback);},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(client=>!client.archived);}});
  return {subject,calls,waitConfirm:()=>confirmPromise,getCapturedBlob:()=>capturedBlob};
}

{
  const old=Array.from({length:5},(_,i)=>({id:`old-${i}`,name:`Old ${i}`,payload:{clients:[]}}));const {subject,calls}=makeRuntime({backupSnapshots:old});const snap=subject.createBackupSnapshot(false);
  eq(subject.backupSnapshots.length,5,'snapshot cap');ok(subject.backupSnapshots[0]===snap,'snapshot newest first');eq(snap.backupDate,'2026-09-01','snapshot date');
  eq(snap.payload.version,'growth-ops-cloud-backup-v4-redacted','snapshot version');eq(snap.payload.redacted,true,'snapshot redacted marker');ok(!('authUsers' in snap.payload),'snapshot auth isolation');ok(!('backupSnapshots' in snap.payload),'snapshot nesting isolation');
  ok(!('loginAccount' in snap.payload.clients[0]),'snapshot loginAccount redacted');ok(!('password' in snap.payload.clients[0]),'snapshot password redacted');ok(!('twoFactor' in snap.payload.clients[0].nested),'snapshot 2FA redacted');
  eq(calls.persist,1,'silent protection snapshot persist signal');eq(calls.storage,1,'snapshot storage');eq(calls.audit.length,0,'silent snapshot audit');eq(calls.fetch,0,'silent protection snapshot network remains deferred for enclosing atomic operation');
}
{
  const {subject,calls}=makeRuntime();const pending=subject.createBackupSnapshot(true);ok(pending&&typeof pending.then==='function','manual snapshot create async ACK');ok(!calls.notify.includes('已创建云端数据快照'),'manual snapshot notice waits for ACK');await pending;
  eq(calls.audit[0][0],'创建数据快照','snapshot audit');eq(calls.notify.at(-1),'已创建云端数据快照','snapshot notice after ACK');eq(calls.fetch,1,'manual snapshot create acknowledged save');
}
{
  const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[{id:'a',name:'A'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);eq(subject.backupSnapshots.length,1,'non-admin delete');eq(calls.confirm.length,0,'non-admin confirm');eq(calls.persist,0,'non-admin persist');eq(calls.fetch,0,'non-admin delete network');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[{id:'a',name:'A'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);await waitConfirm();eq(subject.backupSnapshots.length,1,'cancel delete');eq(calls.persist,0,'cancel delete persist');eq(calls.fetch,0,'cancel delete network');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:[{id:'a',name:'A'},{id:'b',name:'B'}]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);await waitConfirm();eq(subject.backupSnapshots.length,1,'delete length');eq(subject.backupSnapshots[0].id,'b','delete scope');eq(calls.audit.length,1,'delete audit');eq(calls.notify.at(-1),'云端快照已删除','delete notice after ACK');eq(calls.fetch,1,'manual snapshot delete acknowledged save');
}

const restorePayload={clients:[{id:'client-restored',name:'Restored Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],
  financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{restored:true},mediaTools:[],auditLogs:[{id:'audit-restored'}],authUsers:[{id:'attacker-user'}],backupSnapshots:[{id:'nested-attacker'}]};
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls}=makeRuntime({role:'OPS',backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);eq(subject.clients[0].id,'client-before','non-admin restore');eq(calls.confirm.length,0,'non-admin restore confirm');eq(calls.fetch,0,'non-admin restore network');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls,waitConfirm}=makeRuntime({confirm:false,backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);await waitConfirm();eq(subject.clients[0].id,'client-before','cancel restore');eq(calls.persist,0,'cancel restore persist');eq(calls.fetch,0,'cancel restore network');
}
{
  const snap={id:'restore-a',name:'Restore A',payload:restorePayload};const {subject,calls,waitConfirm}=makeRuntime({backupSnapshots:[snap]});subject.restoreBackupSnapshot(snap);await waitConfirm();eq(subject.clients[0].id,'client-restored','restore client');eq(subject.clients[0].normalizedClient,true,'restore normalize');
  eq(subject.authUsers[0].id,'admin-current','restore auth isolation');ok(subject.backupSnapshots.length>=2,'restore protection snapshot');eq(subject.sopProgress.restored,true,'restore SOP');eq(calls.audit.at(-1)[0],'恢复数据快照','restore audit');eq(calls.notify.at(-1),'数据快照已恢复并同步云端','restore notice');ok(calls.persist>=2,'restore mutation persist signals');eq(calls.fetch,1,'restore acknowledged final cloud save');
}

{
  const {subject,calls,getCapturedBlob}=makeRuntime();subject.downloadFullBackup();eq(calls.click,1,'export click');eq(calls.remove,1,'export cleanup');eq(calls.revoke.length,1,'export revoke');const exported=JSON.parse(await getCapturedBlob().text());
  eq(exported.version,'growth-ops-cloud-backup-v4-redacted','export version');eq(exported.redacted,true,'export redacted');ok(!('authUsers' in exported),'export auth isolation');ok(!('backupSnapshots' in exported),'export nesting isolation');ok(!('loginAccount' in exported.clients[0]),'export login redaction');ok(!('password' in exported.clients[0]),'export password redaction');
  eq(calls.audit[0][0],'导出脱敏全量备份','export audit');eq(calls.persist,1,'export persist');eq(calls.notify.at(-1),'脱敏业务备份已导出；不包含登录账号、密码、2FA 或恢复码','export notice');eq(calls.fetch,0,'export network');
}

const importPayload={...restorePayload,clients:[{id:'client-restored',name:'Restored Client',loginAccount:'leak@example.test',password:'leak-password',nested:{twoFactor:'leak-2fa'}}]};
{
  const {subject,calls}=makeRuntime({role:'OPS'});const event={target:{files:[{name:'backup.json',contents:JSON.stringify(importPayload)}],value:'selected'}};subject.importFullBackup(event);eq(event.target.value,'','non-admin import clears file');eq(calls.fileReads,0,'non-admin import read');eq(calls.confirm.length,0,'non-admin import confirm');eq(calls.fetch,0,'non-admin import network');
}
{
  const {subject,calls}=makeRuntime();subject.importFullBackup({target:{files:[{name:'bad.json',contents:'{"notClients":true}'}],value:'selected'}});eq(calls.fileReads,1,'invalid import read');eq(calls.confirm.length,0,'invalid import confirm');eq(calls.persist,0,'invalid import persist');ok(calls.notify.at(-1).includes('无效备份文件'),'invalid import notice');eq(calls.fetch,0,'invalid import network');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false});const event={target:{files:[{name:'backup.json',contents:JSON.stringify(importPayload)}],value:'selected'}};subject.importFullBackup(event);await waitConfirm();eq(event.target.value,'','cancel import clears file');eq(calls.confirm.length,1,'cancel import confirm');eq(subject.clients[0].id,'client-before','cancel import state');eq(calls.persist,0,'cancel import persist');eq(calls.fetch,0,'cancel import network');
}
{
  const {subject,calls,waitConfirm}=makeRuntime();const event={target:{files:[{name:'backup.json',contents:JSON.stringify(importPayload)}],value:'selected'}};subject.importFullBackup(event);await waitConfirm();eq(subject.clients[0].id,'client-restored','import client');eq(subject.authUsers[0].id,'admin-current','import auth isolation');
  ok(!('loginAccount' in subject.clients[0]),'import login redaction');ok(!('password' in subject.clients[0]),'import password redaction');ok(!('twoFactor' in subject.clients[0].nested),'import 2FA redaction');ok(subject.backupSnapshots.length>=1,'import protection snapshot');
  eq(calls.audit.at(-1)[0],'导入脱敏全量备份','import audit');eq(calls.audit.at(-1)[1],'backup.json','import filename');eq(calls.notify.at(-1),'脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖','import notice');eq(calls.fetch,1,'import acknowledged final cloud save');
}

console.log('BUSINESS_BACKUP_MUTATIONS_OK: authority=final-cloud-adapter; snapshot=v4-redacted+cap+silent-protection-debounced+manual-ack-save; delete=admin+confirm+id-scope+ack-save; restore=protect+apply+auth-isolated+ack-save; export=redacted+download; import=redacted+admin+parse+confirm+protect+auth-isolated+ack-save; cancel+deny=zero-network');
