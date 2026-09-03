import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_ADAPTER_CONFIRMATION_INTEGRITY_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['vm.deleteAuthUser=','vm.deleteBackupSnapshot=','vm.restoreBackupSnapshot=','vm.importFullBackup=','user-delete=']){
  if(marker==='user-delete=')continue;
  if(!adapter.includes(marker))throw new Error(`BUSINESS_ADAPTER_CONFIRMATION_INTEGRITY_FAILED: authoritative adapter marker missing: ${marker}`);
}
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_ADAPTER_CONFIRMATION_INTEGRITY_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Permanent confirmation-integrity harness: do not start cloud/session boot.\n})();');
const fail=message=>{throw new Error('BUSINESS_ADAPTER_CONFIRMATION_INTEGRITY_FAILED: '+message);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const ok=(value,label)=>{if(!value)fail(label);};

function makeRuntime({backupSnapshots=[],authUsers=null}={}){
  const calls={fetch:[],persist:0,audit:[],notify:[],confirm:[],fileReads:0,storage:0};
  const callbacks=[];
  const subject={};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  class FileReaderMock{result='';onload=null;readAsText(file){calls.fileReads+=1;this.result=String(file?.contents??'');this.onload?.();}}
  const window={__growthOpsVm:subject,__GROWTHOPS_SUPABASE_URL__:'https://example.invalid',__GROWTHOPS_SUPABASE_KEY__:'test-key',location:{hash:'#system'}};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options?.body||'')});throw new Error('synthetic-network-stop');};
  vm.runInNewContext(harnessAdapter,{window,document:{body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})},localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},
    authUsers:authUsers??[{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},{id:'target-user',name:'Target User',role:'OPS',enabled:true}],
    backupSnapshots:backupSnapshots.map(item=>structuredClone(item)),
    clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[],mediaTools:[],sopProgress:{},
    canDeleteAuthUser:user=>String(user?.id)!==String(subject.currentUser?.id)&&subject.authUsers.filter(u=>u.enabled!==false&&u.role==='ADMIN').length>=1,
    roleLabel:value=>String(value||''),askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},
    notify:message=>calls.notify.push(String(message)),logAudit:(...args)=>calls.audit.push(args),persist:()=>{calls.persist+=1;return true;},updateStorageUsage:()=>{calls.storage+=1;},
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{},mediaTools:[],auditLogs:[]}),
    accountUid:prefix=>`${prefix}-integrity-${calls.persist+1}`,localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],
    normalizeClient:value=>({...value,normalizedClient:true}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(c=>!c.archived);}});
  return {subject,calls,callbacks};
}

const targetUser={id:'target-user',name:'Target User',role:'OPS',enabled:true};

// Confirmation-time ADMIN authority is mandatory for server user deletion.
{
  const {subject,calls,callbacks}=makeRuntime();
  subject.deleteAuthUser(targetUser);eq(callbacks.length,1,'user delete confirmation captured');
  subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};await callbacks[0]();
  eq(calls.fetch.length,0,'revoked ADMIN user delete must not reach server');eq(calls.persist,0,'revoked ADMIN user delete persist');eq(calls.audit.length,0,'revoked ADMIN user delete audit');
}
// A live canDeleteAuthUser denial that appears while the dialog is open must win.
{
  const {subject,calls,callbacks}=makeRuntime();
  subject.deleteAuthUser(targetUser);subject.canDeleteAuthUser=()=>false;await callbacks[0]();
  eq(calls.fetch.length,0,'confirmation-time canDelete denial must block RPC');eq(calls.persist,0,'confirmation-time canDelete denial persist');
}
// User identity must still exist in the authoritative loaded list at execution time.
{
  const {subject,calls,callbacks}=makeRuntime();
  subject.deleteAuthUser(targetUser);subject.authUsers=subject.authUsers.filter(u=>u.id!==targetUser.id);await callbacks[0]();
  eq(calls.fetch.length,0,'stale user confirmation must not call RPC');eq(calls.audit.length,0,'stale user confirmation audit');
}

const snapA={id:'snap-a',name:'Snapshot A',payload:{clients:[{id:'from-a',name:'A'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{},mediaTools:[],auditLogs:[]}};
const snapB={id:'snap-a',name:'Snapshot B Live',payload:{clients:[{id:'from-b',name:'B'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{live:true},mediaTools:[],auditLogs:[]}};

// Snapshot deletion must repeat both authority and live-membership checks.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]();
  eq(subject.backupSnapshots.length,1,'revoked ADMIN snapshot delete must preserve target');eq(calls.persist,0,'revoked ADMIN snapshot delete persist');eq(calls.audit.length,0,'revoked ADMIN snapshot delete audit');
}
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});subject.deleteBackupSnapshot(subject.backupSnapshots[0]);subject.backupSnapshots=[];callbacks[0]();
  eq(calls.persist,0,'stale snapshot delete persist');eq(calls.audit.length,0,'stale snapshot delete audit');
}

// Snapshot restore must not start after authority/target loss and must use live replacement payload for the same canonical ID.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});subject.restoreBackupSnapshot(subject.backupSnapshots[0]);subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]();
  eq(subject.clients[0].id,'client-before','revoked ADMIN restore must preserve business state');eq(calls.persist,0,'revoked ADMIN restore persist');
}
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});subject.restoreBackupSnapshot(subject.backupSnapshots[0]);subject.backupSnapshots=[];callbacks[0]();
  eq(subject.clients[0].id,'client-before','stale snapshot restore must preserve state');eq(calls.persist,0,'stale snapshot restore persist');
}
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});subject.restoreBackupSnapshot(subject.backupSnapshots[0]);subject.backupSnapshots=[structuredClone(snapB)];callbacks[0]();
  eq(subject.clients[0].id,'from-b','same-id replacement restore must use live payload');eq(subject.clients[0].normalizedClient,true,'live replacement restore normalization');eq(subject.sopProgress.live,true,'live replacement SOP payload');ok(subject.backupSnapshots.some(s=>String(s.id).startsWith('backup-integrity-')),'restore must create protection snapshot');ok(calls.persist>=2,'valid live restore must persist protection and restored state');eq(calls.audit.at(-1)?.[1],'Snapshot B Live','restore audit must use live snapshot identity');
}

// Parsed import content is local, but overwrite authority must still be ADMIN when confirmed.
{
  const {subject,calls,callbacks}=makeRuntime();const event={target:{files:[{name:'import.json',contents:JSON.stringify({clients:[{id:'imported',name:'Imported'}]})}],value:'selected'}};
  subject.importFullBackup(event);eq(callbacks.length,1,'import confirmation captured');subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]();
  eq(subject.clients[0].id,'client-before','revoked ADMIN import must preserve state');eq(calls.persist,0,'revoked ADMIN import persist');eq(calls.audit.length,0,'revoked ADMIN import audit');
}

console.log('BUSINESS_ADAPTER_CONFIRMATION_INTEGRITY_OK: authority=final-cloud-adapter; user-delete=admin+live-user+can-delete-recheck; snapshot-delete=admin+live-id-recheck; snapshot-restore=admin+live-id+live-payload; import=confirm-time-admin; stale=zero-rpc-persist-audit');
