import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_PROBE_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Logout persistence barrier probe: suppress automatic boot only.\n})();');

const calls={rpc:[],notify:[],audit:[]};
const subject={};
const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
const fetchMock=async(_url,options={})=>{
  const envelope=JSON.parse(String(options?.body||'{}'));
  calls.rpc.push(envelope.rpc);
  if(envelope.rpc==='crm_save_state')return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
  if(envelope.rpc==='crm_logout')return {ok:true,status:200,json:async()=>({ok:true})};
  return {ok:true,status:200,json:async()=>({})};
};
const window={__growthOpsVm:subject,location:{hash:'#system'}};
vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

Object.assign(subject,{
  currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},
  currentPage:'system',
  clients:[{id:'client-unsaved',name:'Unsaved Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:[],mediaTools:[],authUsers:[],sopProgress:{},
  collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:structuredClone(subject.auditLogs),mediaTools:[],authUsers:[],sopProgress:{}}),
  defaultReminderTypes:()=>[],normalizeClient:x=>({...x}),normalizeStandaloneAlert:x=>({...x}),normalizeReminderTypes:x=>x||[],normalizeOpeningProvider:x=>({...x}),normalizeFinanceActualRebates:x=>x||[],normalizeReceivable:x=>({...x}),normalizeFinanceCost:x=>({...x}),normalizeMediaTool:x=>({...x}),restoreSopProgress:()=>{},migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,updateStorageUsage:()=>{},
  logAudit:(action,detail)=>{calls.audit.push([action,detail]);subject.auditLogs.push({action,detail});subject.persist();},
  notify:message=>calls.notify.push(String(message)),
});
Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients;}});

await subject.logout();
const findings=[];
if(calls.rpc.includes('crm_logout'))findings.push('logout RPC executed after final save failed');
if(subject.currentUser===null)findings.push('session/local state cleared after final save failed');
if(subject.clients.length===0)findings.push('unsaved business state destroyed after final save failed');
if(!calls.notify.some(message=>/保存失败|取消退出/.test(message)))findings.push('save failure did not block logout with user-visible explanation');
if(findings.length)throw new Error(`BUSINESS_LOGOUT_PERSISTENCE_BARRIER_PROBE_FINDINGS: count=${findings.length}; ${findings.join(' | ')}`);
console.log('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_PROBE_SAFE');
