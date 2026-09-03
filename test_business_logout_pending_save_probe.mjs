import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_LOGOUT_PENDING_SAVE_PROBE_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['async function flushSave()','vm.logout=async()=>','crm_save_state','crm_logout'])if(!adapter.includes(marker))throw new Error(`BUSINESS_LOGOUT_PENDING_SAVE_PROBE_FAILED: final adapter marker missing: ${marker}`);
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LOGOUT_PENDING_SAVE_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Synthetic logout/save audit harness: suppress automatic boot only.\n})();');

const calls={save:0,logout:0,notify:[],audit:[],saveState:null,unexpected:[]};
const subject={};
const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
const fetchMock=async(url,options={})=>{
  let envelope={};try{envelope=JSON.parse(String(options?.body||'{}'));}catch{}
  if(envelope.rpc==='crm_save_state'){
    calls.save+=1;calls.saveState=envelope.args?.p_state||null;
    return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_LOGOUT_SAVE_FAILED'})};
  }
  if(envelope.rpc==='crm_logout'){
    calls.logout+=1;
    return {ok:true,status:200,json:async()=>({ok:true})};
  }
  calls.unexpected.push(envelope.rpc||String(url));
  return {ok:false,status:500,json:async()=>({message:'UNEXPECTED_RPC'})};
};
const window={__growthOpsVm:subject,location:{hash:'#system'}};
vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

Object.assign(subject,{
  currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',loginForm:{username:'admin',password:'secret'},
  clients:[{id:'client-unsaved',name:'Unsaved Client Change'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:[],mediaTools:[],authUsers:[{id:'admin-current',role:'ADMIN'}],sopProgress:{unsaved:true},
  collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:structuredClone(subject.backupSnapshots),auditLogs:structuredClone(subject.auditLogs),mediaTools:[],sopProgress:structuredClone(subject.sopProgress)}),
  defaultReminderTypes:()=>[],localDateKey:()=> '2026-09-03',ensureDailyBackup:()=>{},
  normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
  migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:value=>{subject.sopProgress=structuredClone(value||{});},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,updateStorageUsage:()=>{},
  notify:message=>calls.notify.push(String(message)),
  logAudit:(action,detail)=>{calls.audit.push([action,detail]);subject.auditLogs.push({id:`audit-${calls.audit.length}`,action,detail});subject.persist();},
});
Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients.filter(c=>!c.archived);}});

await subject.logout();
const failedSaveCaptured=calls.save===1&&calls.saveState?.clients?.[0]?.id==='client-unsaved';
const logoutContinued=calls.logout===1;
const sessionCleared=subject.currentUser===null;
const localStateCleared=Array.isArray(subject.clients)&&subject.clients.length===0;
const saveFailureVisible=calls.notify.some(message=>message.includes('SYNTHETIC_LOGOUT_SAVE_FAILED')||message.includes('云端保存失败'));
if(failedSaveCaptured&&logoutContinued&&sessionCleared&&localStateCleared&&!saveFailureVisible){
  console.error('BUSINESS_LOGOUT_PENDING_SAVE_PROBE_FINDINGS: save-failed=true; logout-rpc=true; session-cleared=true; local-state-cleared=true; save-failure-visible=false');
  console.error(' - logout swallows the failed pending cloud save, still revokes the session, and clears the unsynchronized local business state');
  process.exitCode=1;
}else{
  console.log(`BUSINESS_LOGOUT_PENDING_SAVE_PROBE_OK: save-failed=${failedSaveCaptured}; logout-rpc=${calls.logout}; session-cleared=${sessionCleared}; local-cleared=${localStateCleared}; failure-visible=${saveFailureVisible}`);
}
