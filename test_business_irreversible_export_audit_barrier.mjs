import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const adapterPath=path.join(root,'dist','cloud-adapter.js');
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: final cloud-adapter missing');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: dist/app missing');
const adapter=fs.readFileSync(adapterPath,'utf8');
for(const marker of ['async function flushSave()','vm.persistExportAuditBarrier=async','vm.downloadFullBackup=async','导出已取消，审计记录未能保存']){
  if(!adapter.includes(marker))throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: final adapter marker missing: ${marker}`);
}
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n  // Permanent irreversible-export harness: suppress automatic boot only.\n})();');

const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
const fail=message=>{throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FAILED: '+message);};
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

function makeRuntime({outcomes=['success'],appendUnrelatedOnFailure=false}={}){
  const calls={fetch:[],notify:[],events:[],xlsx:[],revoke:[]};
  let outcomeIndex=0,auditId=0;
  const subject={};
  const unrelated={id:'audit-unrelated-during-export-save',action:'等待期间合法审计',detail:'preserve'};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const document={
    documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},
    createElement:()=>({href:'',download:'',click(){calls.events.push('backup-file');},remove(){}}),
  };
  const fetchMock=async(url,options={})=>{
    const call={url:String(url),body:String(options?.body||'')};calls.fetch.push(call);
    const outcome=outcomes[Math.min(outcomeIndex++,outcomes.length-1)]||'success';
    if(outcome==='fail'){
      if(appendUnrelatedOnFailure)subject.auditLogs.push(unrelated);
      calls.events.push('save-failed');
      return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_EXPORT_AUDIT_SAVE_FAILED'})};
    }
    calls.events.push('save-ack');
    return {ok:true,status:200,json:async()=>({revision:outcomeIndex})};
  };
  const window={__growthOpsVm:subject,location:{hash:'#system'}};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=> 'blob:export-barrier',revokeObjectURL:url=>calls.revoke.push(String(url))},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});

  const XLSX={utils:{book_new:()=>({syntheticWorkbook:true})},writeFile:(wb,filename,opts)=>{calls.xlsx.push({wb,filename,opts});calls.events.push('xlsx-file');}};
  const appMethods=vm.runInNewContext(`({${['exportFinanceExcel','exportRebateExcel'].map(extract).join(',')}})`,{XLSX,String,Number,Boolean,Array,Object,JSON,Math,Date,Error,Set,Map,Promise,structuredClone},{timeout:1000});

  Object.assign(subject,appMethods,{
    currentUser:{id:'admin-current',name:'Current Admin',role:'ADMIN',enabled:true},currentPage:'system',
    clients:[],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:[],auditLogs:[{id:'audit-before',action:'before'}],mediaTools:[],authUsers:[{id:'admin-current',role:'ADMIN'}],sopProgress:{},
    collectBackupPayload:()=>({clients:structuredClone(subject.clients),standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:structuredClone(subject.openingProviders),openingDeals:structuredClone(subject.openingDeals),financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},backupSnapshots:structuredClone(subject.backupSnapshots),auditLogs:structuredClone(subject.auditLogs),mediaTools:[],authUsers:structuredClone(subject.authUsers),sopProgress:{}}),
    localDateKey:()=> '2026-09-03',defaultReminderTypes:()=>[],ensureDailyBackup:()=>{},
    normalizeClient:value=>({...value}),normalizeStandaloneAlert:value=>({...value}),normalizeReminderTypes:value=>structuredClone(value||[]),normalizeOpeningProvider:value=>({...value}),normalizeFinanceActualRebates:value=>structuredClone(value||[]),normalizeReceivable:value=>({...value}),normalizeFinanceCost:value=>({...value}),normalizeMediaTool:value=>({...value}),
    migrateLegacyAccountSpendRecords:()=>{},migrateOpeningDeals:()=>{},migrateLegacyActualRebatesToReconciliations:()=>{},ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureAutomaticOpeningFeeCosts:()=>{},ensureReceivableLinkedCosts:()=>{},ensureFinanceSnapshotsForLocks:()=>{},restoreSopProgress:()=>{},syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},canViewPage:()=>true,
    logAudit:(action,detail)=>{const row={id:`audit-export-${++auditId}`,action,detail};subject.auditLogs.push(row);return row;},notify:message=>calls.notify.push(String(message)),
    canManageFinance:()=>true,canManageProviders:()=>true,excelLibraryReady:()=>true,excelAppendJsonSheet:()=>{},excelSafeFilePart:value=>String(value).replace(/[^\w\u4e00-\u9fff-]+/g,'_'),
    financePeriodLabel:'2026-09',financeClientFilter:'ALL',financeProviderFilter:'ALL',financeTotals:{spend:{},expected:{},actual:{}},financeReceivableTotals:{expected:{},paid:{},unpaid:{}},financeCostGroups:{},financeExpectedNetProfitGroups:{},financeActualNetProfitGroups:{},financeCashReceivedGroups:{},financeTotalAdSpendGroups:{},financeAttributedSpendGroups:{},financeUnassignedSpendGroups:{},financeNoRebateSpendGroups:{},financeActualProfitLabel:'待确认',financeRows:[],financeVisibleReceivables:[],financeVisibleCosts:[],financeReconciliationRows:[],
    openingSpendPeriodLabel:'2026-09',openingSelectedProviderName:'全部开户商',openingSpendPeriod:'MONTH',openingMonthKey:'2026-09',openingQuarter:3,openingQuarterYear:'2026',openingYear:'2026',openingProviderFilter:'ALL',filteredOpeningDeals:[],filteredOpeningProviders:[],openingDealsFinancialsForPeriod:()=>({spendGroups:{},rebateGroups:{}}),contactCurrentRebateRate:()=>0,rebatePolicyForContact:()=>null,
  });
  Object.defineProperty(subject,'activeClients',{configurable:true,get(){return subject.clients;}});
  return {subject,calls,unrelated};
}

async function assertAppExportSuccess(method,label){
  const {subject,calls}=makeRuntime({outcomes:['success']});
  const pending=subject[method]();
  ok(pending&&typeof pending.then==='function',`${label} exposes audit-barrier completion`);
  eq(calls.xlsx.length,0,`${label} no file before ACK`);
  await pending;
  eq(calls.fetch.length,1,`${label} one acknowledged audit save`);
  eq(calls.xlsx.length,1,`${label} one file after ACK`);
  ok(calls.events.indexOf('save-ack')>=0&&calls.events.indexOf('save-ack')<calls.events.indexOf('xlsx-file'),`${label} save ACK precedes file`);
  const saved=parseSave(calls.fetch[0]);
  eq(saved.auditLogs.length,2,`${label} durable state contains export audit`);
  ok(String(saved.auditLogs[1]?.action||'').includes('导出'),`${label} durable row is export audit`);
}

async function assertAppExportFailure(method,label){
  const {subject,calls,unrelated}=makeRuntime({outcomes:['fail','success'],appendUnrelatedOnFailure:true});
  await subject[method]();
  eq(calls.fetch.length,1,`${label} failed audit save attempt`);
  eq(calls.xlsx.length,0,`${label} zero file on audit save failure`);
  eq(subject.auditLogs.length,2,`${label} only baseline+unrelated audits remain`);
  ok(subject.auditLogs.includes(unrelated),`${label} unrelated concurrent audit preserved`);
  ok(calls.notify.at(-1).includes('导出已取消，审计记录未能保存'),`${label} explicit blocked-export notice`);
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,`${label} later ordinary persist`);
  const later=parseSave(calls.fetch[1]);
  eq(later.auditLogs.length,2,`${label} later save cannot resurrect failed export audit`);
  ok(later.auditLogs.some(row=>row?.id==='audit-unrelated-during-export-save'),`${label} later save keeps unrelated audit`);
  ok(!later.auditLogs.some(row=>String(row?.action||'').includes('导出')),`${label} later save has no false export audit`);
}

await assertAppExportSuccess('exportFinanceExcel','finance export');
await assertAppExportFailure('exportFinanceExcel','finance export');
await assertAppExportSuccess('exportRebateExcel','rebate export');
await assertAppExportFailure('exportRebateExcel','rebate export');

// Redacted full backup uses the same final adapter barrier and may click only after the audit save ACK.
{
  const {subject,calls}=makeRuntime({outcomes:['success']});
  const pending=subject.downloadFullBackup();
  ok(pending&&typeof pending.then==='function','backup export exposes acknowledged completion');
  eq(calls.events.filter(x=>x==='backup-file').length,0,'backup no file before ACK');
  await pending;
  eq(calls.fetch.length,1,'backup one acknowledged audit save');
  eq(calls.events.filter(x=>x==='backup-file').length,1,'backup one file after ACK');
  ok(calls.events.indexOf('save-ack')<calls.events.indexOf('backup-file'),'backup save ACK precedes file');
  const saved=parseSave(calls.fetch[0]);
  eq(saved.auditLogs.filter(row=>row?.action==='导出脱敏全量备份').length,1,'backup durable export audit');
}
{
  const {subject,calls,unrelated}=makeRuntime({outcomes:['fail','success'],appendUnrelatedOnFailure:true});
  await subject.downloadFullBackup();
  eq(calls.fetch.length,1,'backup failed audit save attempt');
  eq(calls.events.filter(x=>x==='backup-file').length,0,'backup zero file on audit save failure');
  eq(calls.revoke.length,1,'backup object URL revoked on blocked export');
  ok(subject.auditLogs.includes(unrelated),'backup failure preserves unrelated concurrent audit');
  ok(!subject.auditLogs.some(row=>row?.action==='导出脱敏全量备份'),'backup failure removes attempt audit');
  subject.persist();await sleep(230);
  eq(calls.fetch.length,2,'backup later ordinary persist');
  const later=parseSave(calls.fetch[1]);
  ok(!later.auditLogs.some(row=>row?.action==='导出脱敏全量备份'),'backup later save cannot resurrect false export audit');
  ok(later.auditLogs.some(row=>row?.id==='audit-unrelated-during-export-save'),'backup later save keeps unrelated audit');
}

console.log('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_BARRIER_OK: authority=final-app+final-cloud-adapter; finance+rebate+redacted-backup=audit-ack-before-file; failure=zero-file+attempt-audit-rollback+unrelated-audit-preserved; later-persist=false-export-audit-not-resurrected');
