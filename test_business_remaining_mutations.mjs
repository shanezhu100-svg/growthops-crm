import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd(),appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_REMAINING_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_REMAINING_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_REMAINING_MUTATIONS_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
const names=['applyBackupPayload','exportFinanceExcel','exportRebateExcel','loadData','logout','restoreDismissedAlerts'];
const storage=new Map(),localStorage={getItem:k=>storage.has(String(k))?storage.get(String(k)):null,setItem:(k,v)=>storage.set(String(k),String(v)),removeItem:k=>storage.delete(String(k)),clear:()=>storage.clear()};
const xlsxCalls=[];
const XLSX={utils:{book_new:()=>({syntheticWorkbook:true})},writeFile:(wb,filename,opts)=>xlsxCalls.push({wb,filename,opts})};
const seedClients=[{id:'seed-client',name:'Seed Client'}],seedAlerts=[{id:'seed-tool',typeKey:'TOOL'},{id:'seed-alert',typeKey:'CUSTOM'}],seedLeads=[{id:'seed-lead'}],seedOpeningProviders=[{id:'seed-provider'}],seedOpeningDeals=[{id:'seed-deal'}],seedAuthUsers=[{id:'seed-admin',name:'Seed Admin',role:'ADMIN',enabled:true}],seedMediaTools=[{id:'seed-tool-media'}];
const context={String,Number,Boolean,Array,Object,JSON,Math,Date,Error,Set,Map,structuredClone,localStorage,XLSX,seedClients,seedAlerts,seedLeads,seedOpeningProviders,seedOpeningDeals,seedAuthUsers,seedMediaTools};
const methods=vm.runInNewContext(`({${names.map(extract).join(',')}})`,context,{timeout:1000});
for(const name of names)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_REMAINING_MUTATIONS_FAILED: ${name} not executable`);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_REMAINING_MUTATIONS_FAILED: ${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const ok=(value,label)=>{if(!value)throw new Error(`BUSINESS_REMAINING_MUTATIONS_FAILED: ${label}`);};
const count=(calls,type)=>calls.filter(x=>x[0]===type).length;
const reset=()=>{storage.clear();xlsxCalls.splice(0);};

function baseSubject(overrides={}){
  const calls=[];let confirmCallback=null;
  const subject={
    ...methods,currentUser:{id:'admin-1',name:'Admin One',role:'ADMIN',enabled:true},currentPage:'system',loginForm:{username:'u',password:'p'},
    clients:[],standaloneAlerts:[],reminderTypes:[],dismissedAlerts:[],leads:[],openingProviders:[],openingDeals:[],financeActualRebates:[],financeReceivables:[],financeCosts:[],financeReconciliations:[],financeMonthLocks:{},financeMonthSnapshots:{},authUsers:[{id:'admin-1',name:'Admin One',role:'ADMIN',enabled:true}],auditLogs:[],mediaTools:[],
    normalizeClient:v=>({...v,normalizedClient:true}),normalizeStandaloneAlert:v=>({...v,normalizedAlert:true}),normalizeReminderTypes:v=>structuredClone(v||[]),defaultReminderTypes:()=>[{key:'RENEWAL',label:'Renewal'}],normalizeOpeningProvider:v=>({...v,normalizedProvider:true}),normalizeFinanceActualRebates:v=>structuredClone(v||[]),normalizeReceivable:v=>({...v,normalizedReceivable:true}),normalizeFinanceCost:v=>({...v,normalizedCost:true}),normalizeMediaTool:v=>({...v,normalizedTool:true}),
    migrateLegacyAccountSpendRecords:()=>calls.push(['migrate-spend']),migrateOpeningDeals:()=>calls.push(['migrate-opening']),migrateLegacyActualRebatesToReconciliations:()=>calls.push(['migrate-rebate']),restoreSopProgress:v=>calls.push(['restore-sop',structuredClone(v||{})]),ensureReceivableLinkedCosts:()=>calls.push(['ensure-cost']),ensureFinanceSnapshotsForLocks:()=>calls.push(['ensure-snapshot']),syncAnalyticsAccountSelection:()=>calls.push(['sync-analytics']),syncAdsAccountSelection:()=>calls.push(['sync-ads']),syncSopAccountSelection:v=>calls.push(['sync-sop',v]),
    persist:()=>{calls.push(['persist']);return true;},persistExportAuditBarrier:async rows=>{calls.push(['export-barrier',Array.isArray(rows)?rows.length:0]);return true;},logAudit:(...a)=>calls.push(['audit',...a]),notify:(...a)=>calls.push(['notify',...a]),askConfirm:(spec,cb)=>{calls.push(['confirm',spec]);confirmCallback=cb;},
    autoDueReminderStage:date=>date?{reminderIndex:2}:null,financeReceivableUnpaid:r=>Number(r.unpaid??r.amount??0),
    canManageFinance:()=>true,canManageProviders:()=>true,excelLibraryReady:()=>true,excelAppendJsonSheet:(wb,name,rows,widths)=>calls.push(['sheet',name,rows.length,widths.length]),excelSafeFilePart:v=>String(v).replace(/[^\w\u4e00-\u9fff-]+/g,'_'),
    financePeriodLabel:'2026-09',financeClientFilter:'ALL',financeProviderFilter:'ALL',financeTotals:{spend:{},expected:{},actual:{}},financeReceivableTotals:{expected:{},paid:{},unpaid:{}},financeCostGroups:{},financeExpectedNetProfitGroups:{},financeActualNetProfitGroups:{},financeCashReceivedGroups:{},financeTotalAdSpendGroups:{},financeAttributedSpendGroups:{},financeUnassignedSpendGroups:{},financeNoRebateSpendGroups:{},financeActualProfitLabel:'待确认',financeRows:[],financeVisibleReceivables:[],financeVisibleCosts:[],financeReconciliationRows:[],
    openingSpendPeriodLabel:'2026-09',openingSelectedProviderName:'全部开户商',openingSpendPeriod:'MONTH',openingMonthKey:'2026-09',openingQuarter:3,openingQuarterYear:'2026',openingYear:'2026',openingProviderFilter:'ALL',filteredOpeningDeals:[],
    ...overrides,
  };
  return {subject,calls,getConfirm:()=>confirmCallback};
}

// App-runtime backup apply: reject structurally invalid or admin-lockout payloads before mutation.
{
  reset();const {subject,calls}=baseSubject({clients:[{id:'before'}]});let threw=false;try{subject.applyBackupPayload({bad:true});}catch(e){threw=String(e.message).includes('无效备份');}
  ok(threw,'invalid backup rejected');eq(subject.clients[0].id,'before','invalid backup leaves clients');eq(count(calls,'persist'),0,'invalid backup no persist');
}
{
  reset();const {subject,calls}=baseSubject({clients:[{id:'before'}]});let threw=false;try{subject.applyBackupPayload({clients:[],authUsers:[{id:'ops',role:'OPS',enabled:true}]});}catch(e){threw=String(e.message).includes('没有启用状态的管理员');}
  ok(threw,'admin-lockout backup rejected');eq(subject.clients[0].id,'before','admin-lockout leaves clients');eq(count(calls,'persist'),0,'admin-lockout no persist');
}
{
  reset();localStorage.setItem('growthOpsSessionUser','admin-1');const {subject,calls}=baseSubject();
  subject.applyBackupPayload({clients:[{id:'restored'}],standaloneAlerts:[{id:'a'}],reminderTypes:[{key:'CUSTOM'}],dismissedAlerts:[{key:'k'}],leads:[{id:'l'}],openingProviders:[{id:'p'}],openingDeals:[{id:'d'}],financeActualRebates:[{id:'r'}],financeReceivables:[{id:'recv'}],financeCosts:[{id:'cost'}],financeReconciliations:[{id:'recon'}],financeMonthLocks:{'2026-09':true},financeMonthSnapshots:{'2026-09':{locked:true}},sopProgress:{step:true},mediaTools:[{id:'m'}],authUsers:[{id:'admin-1',name:'Restored Admin',role:'ADMIN',enabled:true}],auditLogs:[{id:'audit'}]});
  eq(subject.clients[0].normalizedClient,true,'backup normalizes clients');eq(subject.financeReconciliations[0].status,'CONFIRMED','backup defaults reconciliation status');eq(subject.currentUser.id,'admin-1','backup restores enabled matching session');eq(localStorage.getItem('growthOpsSessionUser'),'admin-1','backup preserves valid session key');
  for(const type of ['migrate-spend','migrate-opening','migrate-rebate','restore-sop','ensure-cost','ensure-snapshot','sync-analytics','sync-ads','sync-sop'])eq(count(calls,type),1,`backup ${type} once`);eq(count(calls,'persist'),1,'backup persist once');
}
{
  reset();localStorage.setItem('growthOpsSessionUser','admin-1');const {subject}=baseSubject();subject.applyBackupPayload({clients:[],authUsers:[{id:'admin-2',role:'ADMIN',enabled:true}]});eq(subject.currentUser,null,'backup clears missing session');eq(localStorage.getItem('growthOpsSessionUser'),null,'backup removes stale session key');eq(subject.currentPage,'dashboard','backup returns logged-out page to dashboard');
}

// loadData executes the shipped local fallback semantics, including TOOL alert filtering and all-or-seed fallback on malformed JSON.
{
  reset();localStorage.setItem('growthOpsClients',JSON.stringify([{id:'c1'}]));localStorage.setItem('growthOpsAlerts',JSON.stringify([{id:'tool',typeKey:'TOOL'},{id:'keep',typeKey:'CUSTOM'}]));localStorage.setItem('growthOpsReminderTypes',JSON.stringify([{key:'CUSTOM'}]));localStorage.setItem('growthOpsDismissedAlerts',JSON.stringify([{key:'dismiss'}]));localStorage.setItem('growthOpsLeads',JSON.stringify([{id:'lead'}]));localStorage.setItem('growthOpsOpeningProviders',JSON.stringify([{id:'provider'}]));localStorage.setItem('growthOpsOpeningDeals',JSON.stringify([{id:'deal'}]));localStorage.setItem('growthOpsFinanceActualRebates','[]');localStorage.setItem('growthOpsFinanceReceivables',JSON.stringify([{id:'recv'}]));localStorage.setItem('growthOpsFinanceCosts',JSON.stringify([{id:'cost'}]));localStorage.setItem('growthOpsFinanceReconciliations',JSON.stringify([{id:'recon'}]));localStorage.setItem('growthOpsFinanceMonthLocks','{}');localStorage.setItem('growthOpsFinanceMonthSnapshots','{}');localStorage.setItem('growthOpsAuthUsers',JSON.stringify([{id:'u1',enabled:true}]));localStorage.setItem('growthOpsBackups','[]');localStorage.setItem('growthOpsAuditLogs','[]');localStorage.setItem('growthOpsSessionUser','u1');localStorage.setItem('growthOpsMediaTools',JSON.stringify([{id:'media'}]));
  const {subject}=baseSubject();subject.loadData();eq(subject.clients[0].id,'c1','load clients');eq(subject.standaloneAlerts.length,1,'load filters TOOL alerts');eq(subject.standaloneAlerts[0].id,'keep','load keeps business alert');eq(subject.financeReconciliations[0].status,'CONFIRMED','load defaults reconciliation status');eq(subject.currentUser.id,'u1','load restores enabled session');eq(subject.mediaTools[0].normalizedTool,true,'load normalizes media tools');
}
{
  reset();localStorage.setItem('growthOpsClients','{bad json');const {subject}=baseSubject();subject.loadData();eq(subject.clients[0].id,'seed-client','malformed local fallback resets clients to seed');eq(subject.standaloneAlerts.length,1,'malformed fallback filters seed TOOL alert');eq(subject.currentUser,null,'malformed fallback clears app session');eq(subject.mediaTools[0].id,'seed-tool-media','malformed fallback restores seed media tools');
}

// logout app method: local UI/session cleanup and audit behavior remain stable.
{
  reset();localStorage.setItem('growthOpsSessionUser','admin-1');const {subject,calls}=baseSubject();subject.logout();eq(subject.currentUser,null,'logout clears current user');eq(localStorage.getItem('growthOpsSessionUser'),null,'logout clears local session marker');eq(subject.loginForm.username,'','logout clears username');eq(subject.loginForm.password,'','logout clears password');eq(subject.currentPage,'dashboard','logout navigates dashboard');eq(count(calls,'audit'),1,'logout audits active user once');
}
{
  reset();const {subject,calls}=baseSubject({currentUser:null});subject.logout();eq(count(calls,'audit'),0,'logout without active user has no audit');
}

// Excel exports: permissions/library gates precede generation; valid state waits for the audit barrier, then writes once.
{
  reset();const {subject,calls}=baseSubject({canManageFinance:()=>false});await subject.exportFinanceExcel();eq(xlsxCalls.length,0,'finance export denied no file');eq(count(calls,'audit'),0,'finance export denied no audit');eq(count(calls,'notify'),1,'finance export denied notice');
}
{
  reset();const {subject,calls}=baseSubject({excelLibraryReady:()=>false});await subject.exportFinanceExcel();eq(xlsxCalls.length,0,'finance export missing library no file');eq(count(calls,'audit'),0,'finance export missing library no audit');
}
{
  reset();const {subject,calls}=baseSubject();await subject.exportFinanceExcel();eq(xlsxCalls.length,1,'finance export writes one workbook');eq(xlsxCalls[0].filename,'财务核算_2026-09_全部客户.xlsx','finance export filename');eq(xlsxCalls[0].opts.compression,true,'finance export compression');eq(count(calls,'sheet'),6,'finance export six sheets');eq(count(calls,'audit'),1,'finance export audit once');eq(count(calls,'export-barrier'),1,'finance export audit barrier once');eq(count(calls,'notify'),1,'finance export success notice');
}
{
  reset();const {subject,calls}=baseSubject({canManageProviders:()=>false});await subject.exportRebateExcel();eq(xlsxCalls.length,0,'rebate export denied no file');eq(count(calls,'audit'),0,'rebate export denied no audit');eq(count(calls,'notify'),1,'rebate export denied notice');
}
{
  reset();const {subject,calls}=baseSubject();await subject.exportRebateExcel();eq(xlsxCalls.length,1,'rebate export writes one workbook');eq(xlsxCalls[0].filename,'返点统计_2026-09_全部开户商.xlsx','rebate export filename');eq(xlsxCalls[0].opts.compression,true,'rebate export compression');eq(count(calls,'sheet'),5,'rebate export five sheets');eq(count(calls,'audit'),1,'rebate export audit once');eq(count(calls,'export-barrier'),1,'rebate export audit barrier once');eq(count(calls,'notify'),1,'rebate export success notice');
}

// Reminder restore: valid current-stage rows are restored, unrelated dismissals survive.
{
  reset();const date='2026-09-10',clients=[{id:'c1',endDate:date,archived:false,networkEnvironments:[{id:'ip1',ipDueDate:date}]}],financeReceivables=[{id:'r1',dueDate:date,unpaid:100}],dismissedAlerts=[{key:`CONTRACT-c1|${date}|2`},{key:`IP-c1-ip1|${date}|2`},{key:`RECEIVABLE-r1|${date}|2`},{key:'UNRELATED'}];
  const {subject,calls,getConfirm}=baseSubject({clients,financeReceivables,dismissedAlerts});subject.restoreDismissedAlerts();eq(count(calls,'confirm'),1,'restore asks once for active dismissals');getConfirm()();eq(subject.dismissedAlerts.length,1,'restore removes three active dismissals');eq(subject.dismissedAlerts[0].key,'UNRELATED','restore preserves unrelated dismissal');eq(count(calls,'persist'),1,'restore persist once');eq(count(calls,'audit'),1,'restore audit once');ok(String(calls.find(x=>x[0]==='audit')[2]).includes('3 条'),'restore audit live count');
}
{
  reset();const {subject,calls}=baseSubject({dismissedAlerts:[{key:'UNRELATED'}]});subject.restoreDismissedAlerts();eq(count(calls,'confirm'),0,'no active dismissed reminder no confirmation');eq(count(calls,'persist'),0,'no active dismissed reminder no persist');
}

// Confirmation-time state is authoritative. If the originally eligible reminder is no longer active,
// the callback must not resurrect it by removing its dismissed marker using stale pre-confirm keys.
{
  reset();const date='2026-09-10',client={id:'c1',endDate:date,archived:false,networkEnvironments:[]};const dismissed=[{key:`CONTRACT-c1|${date}|2`}];const {subject,calls,getConfirm}=baseSubject({clients:[client],dismissedAlerts:dismissed});subject.restoreDismissedAlerts();eq(count(calls,'confirm'),1,'stale-state case opens confirmation');client.archived=true;getConfirm()();eq(subject.dismissedAlerts.length,1,'inactive-at-confirm reminder stays dismissed');eq(count(calls,'persist'),0,'inactive-at-confirm no persist');eq(count(calls,'audit'),0,'inactive-at-confirm no audit');
}

// A reminder that becomes active only after the modal opened was never in the confirmed target set.
{
  reset();const date='2026-09-10',later='2026-09-11',a={id:'a',endDate:date,archived:false,networkEnvironments:[]},b={id:'b',endDate:'',archived:false,networkEnvironments:[]};const dismissed=[{key:`CONTRACT-a|${date}|2`},{key:`CONTRACT-b|${later}|2`}];const {subject,getConfirm}=baseSubject({clients:[a,b],dismissedAlerts:dismissed});subject.restoreDismissedAlerts();b.endDate=later;getConfirm()();eq(subject.dismissedAlerts.length,1,'newly active reminder remains dismissed');eq(subject.dismissedAlerts[0].key,`CONTRACT-b|${later}|2`,'newly active key not added to prior confirmation');
}

console.log('BUSINESS_REMAINING_MUTATIONS_OK: backup-apply=invalid+admin-lockout+normalize+session; load=stored+seed-fallback; logout=local-session+audit; exports=permission+library+audit-barrier+write; dismissed-restore=active-only+confirm-time-recheck; provenance=final-shipped-vm');
