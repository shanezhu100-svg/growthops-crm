import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['async function flushSave()','vm.restoreBackupSnapshot=','vm.importFullBackup='])if(!adapter.includes(marker))throw new Error(`BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_FAILED: final adapter marker missing: ${marker}`);
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Synthetic persistence-ack audit harness: suppress automatic boot only.\n})();');

function makeRuntime({backupSnapshots=[]}={}){
  const calls={fetch:[],notify:[],audit:[],confirm:[],storage:0};
  const callbacks=[];
  const subject={};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  class FileReaderMock{result='';onload=null;readAsText(file){this.result=String(file?.contents??'');this.onload?.();}}
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options?.body||'')});
    return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:FileReaderMock,Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',
    backupSnapshots:backupSnapshots.map(x=>structuredClone(x)),clients:[{id:'client-before',name:'Before'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[],mediaTools:[],sopProgress:{},authUsers:[],
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:structuredClone(subject.sopProgress),mediaTools:[],auditLogs:[]}),
    accountUid:prefix=>`${prefix}-probe`,localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],ensureDailyBackup:()=>{},
    normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
    askConfirm:(config,callback)=>{calls.confirm.push(config);callbacks.push(callback);},notify:message=>calls.notify.push(String(message)),logAudit:(...args)=>calls.audit.push(args),updateStorageUsage:()=>{calls.storage+=1;},
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(c=>!c.archived);}});
  return {subject,calls,callbacks};
}

const payload={clients:[{id:'client-restored',name:'Restored'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},sopProgress:{restored:true},mediaTools:[],auditLogs:[]};
const snap={id:'snap-a',name:'Snapshot A',payload};
const {subject,calls,callbacks}=makeRuntime({backupSnapshots:[snap]});
subject.restoreBackupSnapshot(subject.backupSnapshots[0]);
if(callbacks.length!==1)throw new Error(`BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_FAILED: restore confirmation callback count=${callbacks.length}`);
const result=callbacks[0]();
if(result&&typeof result.then==='function')await result;
const premature=calls.notify.includes('数据快照已恢复并同步云端')&&calls.fetch.length===0;
await new Promise(resolve=>setTimeout(resolve,260));
const laterFailure=calls.notify.some(message=>message.includes('云端保存失败')&&message.includes('SYNTHETIC_SAVE_FAILED'));
if(premature||laterFailure){
  console.error(`BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_FINDINGS: premature-success=${premature}; later-cloud-failure=${laterFailure}; fetches=${calls.fetch.length}`);
  console.error(' - restore claims cloud synchronization before the debounced save is acknowledged');
  if(laterFailure)console.error(' - the same operation subsequently reports cloud-save failure after already claiming success');
  process.exitCode=1;
}else{
  console.log('BUSINESS_BACKUP_PERSISTENCE_ACK_PROBE_OK: restore success is emitted only after final cloud save acknowledgement');
}
