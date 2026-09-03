import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Temporary snapshot ACK probe: suppress automatic boot only.\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

function makeRuntime({backupSnapshots=[]}={}){
  const calls={fetch:[],notify:[],audit:[],confirm:[]};
  const callbacks=[];
  let uid=0;
  const subject={};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options?.body||'')});
    return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',
    backupSnapshots:backupSnapshots.map(x=>structuredClone(x)),clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[{id:'audit-before',action:'before'}],mediaTools:[],sopProgress:{before:true},authUsers:[{id:'admin-current',role:'ADMIN'}],
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:structuredClone(subject.sopProgress),mediaTools:[],auditLogs:structuredClone(subject.auditLogs),authUsers:structuredClone(subject.authUsers),backupSnapshots:structuredClone(subject.backupSnapshots)}),
    accountUid:prefix=>`${prefix}-probe-${++uid}`,localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],ensureDailyBackup:()=>{},
    normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
    askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},notify:message=>calls.notify.push(String(message)),
    logAudit:(action,detail)=>{calls.audit.push([action,detail]);subject.auditLogs.push({id:`audit-${calls.audit.length}`,action,detail});subject.persist();},updateStorageUsage:()=>{},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients;}});
  return {subject,calls,callbacks};
}

const findings=[];

// Manual create currently claims cloud success before its debounced save is acknowledged.
{
  const {subject,calls}=makeRuntime();
  const created=subject.createBackupSnapshot(true);
  if(calls.notify.includes('已创建云端数据快照'))findings.push('manual snapshot create claims cloud success before save ACK');
  await sleep(260);
  if(calls.fetch.length!==1)throw new Error(`BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FAILED: create expected one failed save attempt; actual=${calls.fetch.length}`);
  if(subject.backupSnapshots.some(x=>String(x.id)===String(created?.id)))findings.push('failed manual snapshot create remains live locally after cloud save failure');
  if(subject.auditLogs.some(x=>x?.action==='创建数据快照'))findings.push('failed manual snapshot create leaves success audit locally');
}

// Manual delete has the same gap after confirmation.
{
  const original={id:'snapshot-delete-probe',name:'Snapshot Delete Probe',payload:{clients:[{id:'before'}]}};
  const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[original]});
  subject.deleteBackupSnapshot(subject.backupSnapshots[0]);
  if(callbacks.length!==1)throw new Error(`BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FAILED: delete confirmation count=${callbacks.length}`);
  callbacks[0]();
  if(calls.notify.includes('云端快照已删除'))findings.push('manual snapshot delete claims cloud success before save ACK');
  await sleep(260);
  if(calls.fetch.length!==1)throw new Error(`BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FAILED: delete expected one failed save attempt; actual=${calls.fetch.length}`);
  if(!subject.backupSnapshots.some(x=>String(x.id)===String(original.id)))findings.push('failed manual snapshot delete remains deleted locally after cloud save failure');
  if(subject.auditLogs.some(x=>x?.action==='删除数据快照'))findings.push('failed manual snapshot delete leaves success audit locally');
}

if(findings.length)throw new Error(`BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(' | ')}`);
console.log('BUSINESS_BACKUP_SNAPSHOT_PERSISTENCE_ACK_PROBE_SAFE');
