import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_PERSISTENCE_ACK_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of [
  'async function flushSave()',
  'function rollbackFailedBusinessOverwrite(before)',
  'await flushSave();',
  '快照恢复失败，云端未变更',
  '备份导入失败，云端未变更',
])if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_PERSISTENCE_ACK_FAILED: final adapter marker missing: ${marker}`);
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_BACKUP_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Permanent save-ack harness: suppress automatic boot only.\n})();');
const fail=message=>{throw new Error('BUSINESS_BACKUP_PERSISTENCE_ACK_FAILED: '+message);};
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

function makeRuntime({backupSnapshots=[],outcomes=['success']}={}){
  const calls={fetch:[],notify:[],audit:[],confirm:[],storage:0};
  const callbacks=[];
  let outcomeIndex=0,uid=0;
  const subject={};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  class FileReaderMock{result='';onload=null;readAsText(file){this.result=String(file?.contents??'');this.onload?.();}}
  const fetchMock=async(url,options={})=>{
    const call={url:String(url),body:String(options?.body||'')};calls.fetch.push(call);
    const outcome=outcomes[Math.min(outcomeIndex++,outcomes.length-1)]||'success';
    if(outcome==='fail')return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
    return {ok:true,status:200,json:async()=>({revision:outcomeIndex})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',
    backupSnapshots:backupSnapshots.map(x=>structuredClone(x)),clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[{id:'audit-before',action:'before'}],mediaTools:[],sopProgress:{before:true},authUsers:[{id:'admin-current',role:'ADMIN'}],
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:structuredClone(subject.standaloneAlerts),reminderTypes:structuredClone(subject.reminderTypes),dismissedAlerts:structuredClone(subject.dismissedAlerts),leads:structuredClone(subject.leads),openingProviders:structuredClone(subject.openingProviders),openingDeals:structuredClone(subject.openingDeals),financeActualRebates:structuredClone(subject.financeActualRebates),financeReceivables:structuredClone(subject.financeReceivables),financeCosts:structuredClone(subject.financeCosts),financeReconciliations:structuredClone(subject.financeReconciliations),financeMonthLocks:structuredClone(subject.financeMonthLocks),financeMonthSnapshots:structuredClone(subject.financeMonthSnapshots),sopProgress:structuredClone(subject.sopProgress),mediaTools:structuredClone(subject.mediaTools),auditLogs:structuredClone(subject.auditLogs),authUsers:structuredClone(subject.authUsers),backupSnapshots:structuredClone(subject.backupSnapshots)}),
    accountUid:prefix=>`${prefix}-ack-${++uid}`,localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],ensureDailyBackup:()=>{},
    normalizeClient:value=>({...value,normalizedClient:true}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
    askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},notify:message=>calls.notify.push(String(message)),
    logAudit:(action,detail)=>{calls.audit.push([action,detail]);subject.auditLogs.push({id:`audit-${calls.audit.length}`,action,detail});subject.persist();},updateStorageUsage:()=>{calls.storage+=1;},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(c=>!c.archived);}});
  return {subject,calls,callbacks};
}

const restoredPayload={clients:[{id:'client-restored',name:'Restored'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{restored:true},mediaTools:[],auditLogs:[{id:'audit-from-snapshot',action:'snapshot'}]};
const snap={id:'snap-a',name:'Snapshot A',payload:restoredPayload};

// Restore: no success until the one atomic final state save is acknowledged.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snap],outcomes:['success']});
  subject.restoreBackupSnapshot(subject.backupSnapshots[0]);eq(callbacks.length,1,'restore confirmation count');
  const pending=callbacks[0]();
  ok(pending&&typeof pending.then==='function','restore confirmation callback must be async');
  ok(!calls.notify.includes('数据快照已恢复并同步云端'),'restore must not claim success synchronously');
  await pending;
  eq(calls.fetch.length,1,'restore must perform exactly one acknowledged cloud save');
  eq(calls.notify.at(-1),'数据快照已恢复并同步云端','restore success must follow cloud ACK');
  const saved=parseSave(calls.fetch[0]);
  eq(saved.clients[0].id,'client-restored','restore saved state');
  const protection=(saved.backupSnapshots||[]).find(item=>String(item.id).startsWith('backup-ack-'));
  ok(protection,'restore final save must contain protection snapshot');
  eq(protection.payload.clients[0].id,'client-before','restore protection snapshot must capture pre-restore business state');
  eq(subject.clients[0].id,'client-restored','restore local state after successful ACK');
}

// Restore failure: no success, local rollback, and a later ordinary persist can only save pre-operation state.
{
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snap],outcomes:['fail','success']});
  subject.restoreBackupSnapshot(subject.backupSnapshots[0]);const pending=callbacks[0]();await pending;
  eq(calls.fetch.length,1,'failed restore first save attempt');
  ok(!calls.notify.includes('数据快照已恢复并同步云端'),'failed restore must never claim success');
  ok(calls.notify.at(-1).includes('快照恢复失败，云端未变更'),'failed restore must state cloud remained unchanged');
  eq(subject.clients[0].id,'client-before','failed restore local clients rollback');
  eq(subject.sopProgress.before,true,'failed restore SOP rollback');
  eq(subject.backupSnapshots.length,1,'failed restore protection snapshot rollback');
  eq(subject.backupSnapshots[0].id,'snap-a','failed restore original snapshot restored');
  eq(subject.auditLogs.length,1,'failed restore success audit rollback');
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,'post-failure ordinary persist attempt');
  const later=parseSave(calls.fetch[1]);
  eq(later.clients[0].id,'client-before','post-failure save must not resurrect failed restored state');
  eq((later.backupSnapshots||[]).length,1,'post-failure save must not contain failed protection snapshot');
}

const importPayload={...restoredPayload,clients:[{id:'client-imported',name:'Imported',loginAccount:'strip-me',password:'strip-me-too'}]};

// Import success has the same single-ACK atomicity and includes the pre-import protection snapshot.
{
  const {subject,calls,callbacks}=makeRuntime({outcomes:['success']});
  const event={target:{files:[{name:'backup.json',contents:JSON.stringify(importPayload)}],value:'selected'}};
  subject.importFullBackup(event);eq(callbacks.length,1,'import confirmation count');
  const pending=callbacks[0]();ok(!calls.notify.some(m=>m.includes('脱敏备份已导入并同步云端')),'import must not claim success synchronously');await pending;
  eq(calls.fetch.length,1,'import must perform exactly one acknowledged cloud save');
  eq(calls.notify.at(-1),'脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖','import success must follow cloud ACK');
  const saved=parseSave(calls.fetch[0]);
  eq(saved.clients[0].id,'client-imported','import saved state');
  ok(!('loginAccount' in saved.clients[0]),'import saved login material must remain redacted');
  ok(!('password' in saved.clients[0]),'import saved password must remain redacted');
  const protection=(saved.backupSnapshots||[]).find(item=>String(item.id).startsWith('backup-ack-'));
  ok(protection,'import final save must contain protection snapshot');
  eq(protection.payload.clients[0].id,'client-before','import protection snapshot must capture pre-import state');
}

// Import failure also rolls back fully and cannot leak failed imported state into a later save.
{
  const {subject,calls,callbacks}=makeRuntime({outcomes:['fail','success']});
  const event={target:{files:[{name:'backup.json',contents:JSON.stringify(importPayload)}],value:'selected'}};
  subject.importFullBackup(event);const pending=callbacks[0]();await pending;
  eq(calls.fetch.length,1,'failed import first save attempt');
  ok(!calls.notify.some(m=>m.includes('脱敏备份已导入并同步云端')),'failed import must never claim success');
  ok(calls.notify.at(-1).includes('备份导入失败，云端未变更'),'failed import must state cloud remained unchanged');
  eq(subject.clients[0].id,'client-before','failed import local clients rollback');
  eq(subject.sopProgress.before,true,'failed import SOP rollback');
  eq(subject.backupSnapshots.length,0,'failed import protection snapshot rollback');
  eq(subject.auditLogs.length,1,'failed import success audit rollback');
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,'post-failure import ordinary persist attempt');
  const later=parseSave(calls.fetch[1]);
  eq(later.clients[0].id,'client-before','post-failure save must not resurrect failed imported state');
  eq((later.backupSnapshots||[]).length,0,'post-failure save must not contain failed import protection snapshot');
}

console.log('BUSINESS_BACKUP_PERSISTENCE_ACK_OK: authority=final-cloud-adapter; restore+import=single-final-save+success-after-ack+atomic-protection; failure=cloud-unchanged+local-prestate-rollback; later-persist=failed-overwrite-not-resurrected');
