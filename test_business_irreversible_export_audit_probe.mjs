import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
const appMethods=vm.runInNewContext(`({${['exportFinanceExcel','exportRebateExcel'].map(extract).join(',')}})`,{String,Number,Boolean,Array,Object,JSON,Math,Date,Error,Set,Map,structuredClone},{timeout:1000});
const findings=[];

function appSubject(kind){
  const events=[];
  const XLSX={utils:{book_new:()=>({})},writeFile:()=>events.push('file-delivered')};
  const subject={
    ...appMethods,
    currentUser:{id:'admin',name:'Admin',role:'ADMIN'},
    canManageFinance:()=>true,canManageProviders:()=>true,excelLibraryReady:()=>true,
    excelAppendJsonSheet:()=>{},excelSafeFilePart:v=>String(v),
    logAudit:()=>events.push('audit-created'),persist:()=>events.push('persist-enqueued'),notify:()=>events.push('success-notice'),
    financePeriodLabel:'2026-09',financeClientFilter:'ALL',financeProviderFilter:'ALL',financeTotals:{spend:{},expected:{},actual:{}},financeReceivableTotals:{expected:{},paid:{},unpaid:{}},financeCostGroups:{},financeExpectedNetProfitGroups:{},financeActualNetProfitGroups:{},financeCashReceivedGroups:{},financeTotalAdSpendGroups:{},financeAttributedSpendGroups:{},financeUnassignedSpendGroups:{},financeNoRebateSpendGroups:{},financeActualProfitLabel:'待确认',financeRows:[],financeVisibleReceivables:[],financeVisibleCosts:[],financeReconciliationRows:[],financeReconciliations:[],
    openingSpendPeriodLabel:'2026-09',openingSelectedProviderName:'全部开户商',openingSpendPeriod:'MONTH',openingMonthKey:'2026-09',openingQuarter:3,openingQuarterYear:'2026',openingYear:'2026',openingProviderFilter:'ALL',openingProviders:[],openingDeals:[],filteredOpeningProviders:[],filteredOpeningDeals:[],
    openingDealsFinancialsForPeriod:()=>({spendGroups:{},rebateGroups:{}}),contactCurrentRebateRate:()=>0,rebatePolicyForContact:()=>null,localDateKey:()=> '2026-09-03',
  };
  const context={XLSX};
  const method=vm.runInNewContext(`({${extract(kind)}})`,context,{timeout:1000})[kind];
  return {subject:{...subject,[kind]:method},events};
}
for(const name of ['exportFinanceExcel','exportRebateExcel']){
  const {subject,events}=appSubject(name);
  subject[name]();
  const file=events.indexOf('file-delivered'),audit=events.indexOf('audit-created');
  if(file<0)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: ${name} did not deliver synthetic file`);
  if(audit<0)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: ${name} did not create audit`);
  if(file<audit)findings.push(`${name}: file delivery occurs before export audit is even created`);
}

const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: final cloud-adapter missing');
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: adapter boot anchor drifted');
const subject={};const events=[];
const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({href:'',download:'',click(){events.push('file-delivered');},remove(){}})};
const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
const window={__growthOpsVm:subject,location:{hash:'#system'}};
vm.runInNewContext(adapter.replace(bootAnchor,'\n})();'),{window,document,localStorage,URL:{createObjectURL:()=> 'blob:probe',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:async()=>({ok:true,status:200,json:async()=>({revision:1})})},{timeout:1000});
Object.assign(subject,{
  currentUser:{id:'admin',name:'Admin',role:'ADMIN'},
  collectBackupPayload:()=>({clients:[],auditLogs:[],backupSnapshots:[],authUsers:[]}),
  localDateKey:()=> '2026-09-03',
  logAudit:()=>events.push('audit-created'),persist:()=>events.push('persist-enqueued'),notify:()=>events.push('success-notice'),
});
subject.downloadFullBackup();
const backupFile=events.indexOf('file-delivered'),backupAudit=events.indexOf('audit-created');
if(backupFile<0||backupAudit<0)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FAILED: full backup event sequence=${events.join(',')}`);
if(backupFile<backupAudit)findings.push('downloadFullBackup: file delivery occurs before export audit is even created');

if(findings.length)throw new Error(`BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_FINDINGS: count=${findings.length}; ${findings.join(' | ')}`);
console.log('BUSINESS_IRREVERSIBLE_EXPORT_AUDIT_PROBE_SAFE');
