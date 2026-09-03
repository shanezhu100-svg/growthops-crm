import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of [
  'async function flushSave()',
  '快照创建失败，云端未变更',
  '快照删除失败，云端未变更',
  'const snapshotAuditRows=',
])if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_FAILED: final adapter marker missing: ${marker}`);
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Permanent manual snapshot ACK harness: suppress automatic boot only.\n})();');
const fail=message=>{throw new Error('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_FAILED: '+message);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const ok=(value,label)=>{if(!value)fail(label);};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

function parseSave(call){
  const envelope=JSON.parse(call.body||'{}');
  eq(envelope.rpc,'crm_save_state','BFF save RPC name');
  const state=envelope.args?.p_state;
  if(!state||typeof state!=='object')fail('BFF save payload missing state');
  return state;
}

function makeRuntime({backupSnapshots=[],outcomes=['success'],appendUnrelatedOnFailure=false}={}){
  const calls={fetch:[],notify:[],audit:[],confirm:[],storage:0};
  const callbacks=[];
  let outcomeIndex=0,uid=0;
  const subject={};
  const unrelated={id:'audit-unrelated-during-save',action:'等待期间合法审计',detail:'preserve'};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    const call={url:String(url),body:String(options?.body||'')};calls.fetch.push(call);
    const outcome=outcomes[Math.min(outcomeIndex++,outcomes.length-1)]||'success';
    if(outcome==='fail'){
      if(appendUnrelatedOnFailure)subject.auditLogs.push(unrelated);
      return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
    }
    return {ok:true,status:200,json:async()=>({revision:outcomeIndex})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',
    backupSnapshots:backupSnapshots.map(x=>structuredClone(x)),clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[{id:'audit-before',action:'before'}],mediaTools:[],sopProgress:{before:true},authUsers:[{id:'admin-current',role:'ADMIN'}],
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:structuredClone(subject.sopProgress),mediaTools:[],auditLogs:structuredClone(subject.auditLogs),authUsers:structuredClone(subject.authUsers),backupSnapshots:structuredClone(subject.backupSnapshots)}),
    accountUid:prefix=>`${prefix}-manual-${++uid}`,localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],ensureDailyBackup:()=>{},
    normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
    askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},notify:message=>calls.notify.push(String(message)),
    logAudit:(action,detail)=>{const row={id:`audit-${calls.audit.length+1}`,action,detail};calls.audit.push([action,detail]);subject.auditLogs.push(row);subject.persist();return row;},updateStorageUsage:()=>{calls.storage+=1;},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients;}});
  return {subject,calls,callbacks,unrelated};
}

const originals=Array.from({length:5},(_,i)=>({id:`old-${i}`,name:`Old ${i}`,payload:{clients:[{id:`old-client-${i}`}]}}));

// Manual create success: one cloud save containing both snapshot and audit, with success only after ACK.
{
  const {subject,calls}=makeRuntime({backupSnapshots:originals,outcomes:['success']});
  const pending=subject.createBackupSnapshot(true);
  ok(pending&&typeof pending.then==='function','manual create must expose acknowledged async completion');
  ok(!calls.notify.includes('已创建云端数据快照'),'manual create must not claim success synchronously');
  const snap=await pending;
  eq(calls.fetch.length,1,'manual create exactly one acknowledged save');
  eq(calls.notify.at(-1),'已创建云端数据快照','manual create success follows ACK');
  const saved=parseSave(calls.fetch[0]);
  eq(saved.backupSnapshots.length,5,'manual create preserves snapshot cap in saved state');
  eq(saved.backupSnapshots[0].id,snap.id,'manual create saves newest snapshot');
  eq(saved.auditLogs.filter(row=>row?.action==='创建数据快照').length,1,'manual create saves one success audit');
}

// Manual create failure: restore all pre-operation snapshots/audits and keep unrelated concurrent audit; later persist cannot resurrect failed create.
{
  const {subject,calls,unrelated}=makeRuntime({backupSnapshots:originals,outcomes:['fail','success'],appendUnrelatedOnFailure:true});
  const result=await subject.createBackupSnapshot(true);
  eq(result,null,'failed manual create returns no committed snapshot');
  eq(calls.fetch.length,1,'failed manual create one save attempt');
  ok(!calls.notify.includes('已创建云端数据快照'),'failed manual create never claims success');
  ok(calls.notify.at(-1).includes('快照创建失败，云端未变更'),'failed manual create cloud-unchanged notice');
  eq(subject.backupSnapshots.map(x=>x.id).join(','),originals.map(x=>x.id).join(','),'failed manual create restores full pre-cap snapshot list');
  eq(subject.auditLogs.filter(row=>row?.action==='创建数据快照').length,0,'failed manual create removes success audit');
  ok(subject.auditLogs.includes(unrelated),'failed manual create preserves unrelated audit added while awaiting save');
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,'post-create-failure ordinary persist attempt');
  const later=parseSave(calls.fetch[1]);
  eq(later.backupSnapshots.map(x=>x.id).join(','),originals.map(x=>x.id).join(','),'later save cannot resurrect failed create');
  eq(later.auditLogs.filter(row=>row?.action==='创建数据快照').length,0,'later save cannot resurrect failed create audit');
  ok(later.auditLogs.some(row=>row?.id==='audit-unrelated-during-save'),'later save retains unrelated concurrent audit');
}

// Manual delete success: confirmation callback is async and persists removal+audit atomically before success notice.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:originals,outcomes:['success']});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  eq(callbacks.length,1,'manual delete confirmation count');
  const pending=callbacks[0]();
  ok(pending&&typeof pending.then==='function','manual delete confirmation callback must be async');
  ok(!calls.notify.includes('云端快照已删除'),'manual delete must not claim success synchronously');
  await pending;
  eq(calls.fetch.length,1,'manual delete exactly one acknowledged save');
  eq(calls.notify.at(-1),'云端快照已删除','manual delete success follows ACK');
  const saved=parseSave(calls.fetch[0]);
  ok(!saved.backupSnapshots.some(x=>x.id==='old-0'),'manual delete saved state removes target');
  eq(saved.auditLogs.filter(row=>row?.action==='删除数据快照').length,1,'manual delete saves one success audit');
}

// Manual delete failure: target/audit roll back, unrelated concurrent audit survives, and later persist keeps the target.
{
  const {subject,calls,callbacks,unrelated}=makeRuntime({backupSnapshots:originals,outcomes:['fail','success'],appendUnrelatedOnFailure:true});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  const pending=callbacks[0]();await pending;
  eq(calls.fetch.length,1,'failed manual delete one save attempt');
  ok(!calls.notify.includes('云端快照已删除'),'failed manual delete never claims success');
  ok(calls.notify.at(-1).includes('快照删除失败，云端未变更'),'failed manual delete cloud-unchanged notice');
  eq(subject.backupSnapshots.map(x=>x.id).join(','),originals.map(x=>x.id).join(','),'failed manual delete restores pre-operation snapshots');
  eq(subject.auditLogs.filter(row=>row?.action==='删除数据快照').length,0,'failed manual delete removes success audit');
  ok(subject.auditLogs.includes(unrelated),'failed manual delete preserves unrelated audit added while awaiting save');
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,'post-delete-failure ordinary persist attempt');
  const later=parseSave(calls.fetch[1]);
  eq(later.backupSnapshots.map(x=>x.id).join(','),originals.map(x=>x.id).join(','),'later save cannot resurrect failed delete');
  eq(later.auditLogs.filter(row=>row?.action==='删除数据快照').length,0,'later save cannot resurrect failed delete audit');
  ok(later.auditLogs.some(row=>row?.id==='audit-unrelated-during-save'),'later save retains unrelated concurrent audit');
}

console.log('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_OK: authority=final-cloud-adapter; manual-create+delete=single-save-ack-before-success; failure=snapshot+attempt-audit-rollback+unrelated-audit-preserved; later-persist=failed-operation-not-resurrected; protection-create=false=separate-atomic-restore-import-path');
