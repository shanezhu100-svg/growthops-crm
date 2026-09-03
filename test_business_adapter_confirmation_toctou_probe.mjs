import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_ADAPTER_CONFIRMATION_TOCTOU_PROBE_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['vm.deleteAuthUser=','vm.deleteBackupSnapshot=','vm.restoreBackupSnapshot=','vm.importFullBackup=']){
  if(!adapter.includes(marker))throw new Error(`BUSINESS_ADAPTER_CONFIRMATION_TOCTOU_PROBE_FAILED: authoritative adapter marker missing: ${marker}`);
}
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_ADAPTER_CONFIRMATION_TOCTOU_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Synthetic confirmation-time audit harness: do not start cloud/session boot.\n})();');

function makeRuntime({backupSnapshots=[],authUsers=null}={}){
  const calls={fetch:[],persist:0,audit:[],notify:[],confirm:[],protect:0,fileReads:0};
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
    clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[],mediaTools:[],
    canDeleteAuthUser:user=>String(user?.id)!==String(subject.currentUser?.id)&&subject.authUsers.filter(u=>u.enabled!==false&&u.role==='ADMIN').length>=1,
    roleLabel:value=>String(value||''),
    askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},
    notify:message=>calls.notify.push(String(message)),logAudit:(...args)=>calls.audit.push(args),persist:()=>{calls.persist+=1;return true;},updateStorageUsage:()=>{},
    collectBackupPayload:()=>({clients:[{id:'client-before',name:'Before'}]}),accountUid:prefix=>`${prefix}-audit`,localDateKey:()=> '2026-09-03',
    defaultReminderTypes:()=>[],normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:()=>{},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(c=>!c.archived);}});
  return {subject,calls,callbacks};
}

const findings=[];
const finding=(name,detail)=>findings.push(`${name}: ${detail}`);
const targetUser={id:'target-user',name:'Target User',role:'OPS',enabled:true};

// User deletion authority must still be valid when the confirmation callback executes.
{
  const {subject,calls,callbacks}=makeRuntime();
  subject.deleteAuthUser(targetUser);subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};await callbacks[0]?.();
  if(calls.fetch.length)finding('deleteAuthUser','confirmation callback sends delete RPC after ADMIN authority is revoked');
}
{
  const {subject,calls,callbacks}=makeRuntime({authUsers:[{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},{...targetUser,role:'ADMIN'}]});
  subject.deleteAuthUser(targetUser);subject.authUsers=[{...subject.currentUser},{...targetUser,role:'ADMIN'}];subject.canDeleteAuthUser=()=>false;await callbacks[0]?.();
  if(calls.fetch.length)finding('deleteAuthUser','confirmation callback ignores a new canDeleteAuthUser denial');
}
{
  const {subject,calls,callbacks}=makeRuntime();
  subject.deleteAuthUser(targetUser);subject.authUsers=subject.authUsers.filter(u=>u.id!==targetUser.id);await callbacks[0]?.();
  if(calls.fetch.length)finding('deleteAuthUser','stale confirmation sends delete RPC after target user disappears from live authUsers');
}

const snapA={id:'snap-a',name:'Snapshot A',payload:{clients:[{id:'from-a',name:'A'}]}};
// Snapshot deletion must re-check ADMIN authority and live membership when confirmed.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]?.();
  if(subject.backupSnapshots.length!==1||calls.persist||calls.audit.length)finding('deleteBackupSnapshot','confirmation callback deletes/persists after ADMIN authority is revoked');
}
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);subject.backupSnapshots=[];callbacks[0]?.();
  if(calls.persist||calls.audit.length)finding('deleteBackupSnapshot','stale confirmation persists/audits after target snapshot already disappeared');
}

// Snapshot restore must re-check authority and re-resolve the live snapshot payload.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});
  subject.restoreBackupSnapshot(subject.backupSnapshots[0]);subject.createBackupSnapshot=()=>{calls.protect+=1;};subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]?.();
  if(calls.protect)finding('restoreBackupSnapshot','confirmation callback starts destructive restore after ADMIN authority is revoked');
}
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snapA]});
  subject.restoreBackupSnapshot(subject.backupSnapshots[0]);subject.createBackupSnapshot=()=>{calls.protect+=1;};subject.backupSnapshots=[];callbacks[0]?.();
  if(calls.protect)finding('restoreBackupSnapshot','stale confirmation starts restore after target snapshot disappears');
}

// Import authority can change after file parsing but before the user confirms overwrite.
{
  const {subject,calls,callbacks}=makeRuntime();
  const event={target:{files:[{name:'import.json',contents:JSON.stringify({clients:[{id:'imported',name:'Imported'}]})}],value:'selected'}};
  subject.importFullBackup(event);subject.createBackupSnapshot=()=>{calls.protect+=1;};subject.currentUser={id:'ops-now',name:'Ops',role:'OPS',enabled:true};callbacks[0]?.();
  if(calls.protect)finding('importFullBackup','confirmation callback starts destructive import after ADMIN authority is revoked');
}

if(findings.length){
  console.error(`BUSINESS_ADAPTER_CONFIRMATION_TOCTOU_PROBE_FINDINGS: count=${findings.length}`);
  for(const item of findings)console.error(` - ${item}`);
  process.exitCode=1;
}else{
  console.log('BUSINESS_ADAPTER_CONFIRMATION_TOCTOU_PROBE_OK: user+backup destructive callbacks revalidate live authority and target state');
}
