import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of [
  'async function flushSave()',
  "await flushSave();}catch(e){if(logoutAuditRows.length&&Array.isArray(vm.auditLogs))",
  "vm.notify(`云端保存失败，已取消退出：",
  "rpc('crm_logout'",
])if(!adapter.includes(marker))throw new Error(`BUSINESS_LOGOUT_PERSISTENCE_BARRIER_FAILED: final adapter marker missing: ${marker}`);
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Permanent logout persistence barrier harness: suppress automatic boot only.\n})();');

const fail=message=>{throw new Error('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_FAILED: '+message);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const ok=(value,label)=>{if(!value)fail(label);};

function makeRuntime(saveOutcome){
  const calls={requests:[],notify:[],audit:[]};
  const subject={};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(_url,options={})=>{
    const envelope=JSON.parse(String(options?.body||'{}'));
    calls.requests.push(structuredClone(envelope));
    if(envelope.rpc==='crm_save_state'){
      if(saveOutcome==='fail')return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_SAVE_FAILED'})};
      return {ok:true,status:200,json:async()=>({revision:1})};
    }
    if(envelope.rpc==='crm_logout')return {ok:true,status:200,json:async()=>({ok:true})};
    return {ok:true,status:200,json:async()=>({})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

  Object.assign(subject,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},
    currentPage:'system',loginForm:{username:'admin-user',password:'unsaved-form-value'},
    clients:[{id:'client-unsaved',name:'Unsaved Client'}],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:[],mediaTools:[],authUsers:[],sopProgress:{},
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:structuredClone(subject.auditLogs),mediaTools:[],authUsers:[],sopProgress:{}}),
    ensureDailyBackup:()=>{},defaultReminderTypes:()=>[],normalizeClient:x=>({...x}),normalizeStandaloneAlert:x=>({...x}),normalizeReminderTypes:x=>x||[],normalizeOpeningProvider:x=>({...x}),normalizeFinanceActualRebates:x=>x||[],normalizeReceivable:x=>({...x}),normalizeFinanceCost:x=>({...x}),normalizeMediaTool:x=>({...x}),restoreSopProgress:()=>{},migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,updateStorageUsage:()=>{},
    logAudit:(action,detail)=>{calls.audit.push([action,detail]);subject.auditLogs.push({action,detail});subject.persist();},
    notify:message=>calls.notify.push(String(message)),
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients;}});
  return {subject,calls};
}

// A failed final cloud save must be a hard barrier: keep the authenticated UI and unsaved CRM state intact.
{
  const {subject,calls}=makeRuntime('fail');
  await subject.logout();
  eq(calls.requests.map(x=>x.rpc).join(','),'crm_save_state',`failed logout RPC sequence; notices=${calls.notify.join(' | ')}`);
  eq(subject.currentUser?.id,'admin-current','failed logout preserves active user');
  eq(subject.clients[0]?.id,'client-unsaved','failed logout preserves unsaved business state');
  eq(subject.currentPage,'system','failed logout preserves route');
  eq(subject.loginForm.username,'admin-user','failed logout preserves login/form state');
  eq(subject.loginForm.password,'unsaved-form-value','failed logout preserves form value');
  ok(calls.notify.some(message=>message.includes('云端保存失败，已取消退出')),'failed logout must explain that logout was cancelled');
  ok(!calls.requests.some(x=>x.rpc==='crm_logout'),'failed save must not revoke server session');
}

// On ACK, the exit audit is included in the saved state before server logout and local cleanup.
{
  const {subject,calls}=makeRuntime('success');
  await subject.logout();
  eq(calls.requests.map(x=>x.rpc).join(','),'crm_save_state,crm_logout',`successful logout RPC order; notices=${calls.notify.join(' | ')}`);
  const save=calls.requests[0];
  const savedState=save.args?.p_state;
  ok(savedState&&Array.isArray(savedState.auditLogs),'successful logout save must include audit state');
  eq(savedState.clients[0]?.id,'client-unsaved','successful logout saves latest business state before revoke');
  eq(savedState.auditLogs.filter(row=>row?.action==='退出系统').length,1,'successful logout saves one exit audit');
  eq(subject.currentUser,null,'successful logout clears current user after ACK');
  eq(subject.clients.length,0,'successful logout clears local business state after ACK');
  eq(subject.currentPage,'dashboard','successful logout returns to dashboard');
  eq(subject.loginForm.username,'','successful logout clears username');
  eq(subject.loginForm.password,'','successful logout clears password');
  eq(calls.audit.length,1,'successful logout creates one exit audit');
}

console.log('BUSINESS_LOGOUT_PERSISTENCE_BARRIER_OK: authority=final-cloud-adapter; active-logout=exit-audit+save-ack-before-session-revoke; save-failure=cancel+session+business-state+route+form-preserved+notice; save-success=save-then-server-logout+local-clear');
