import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_CLIENT_STATUS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_CLIENT_STATUS_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_CLIENT_STATUS_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_CLIENT_STATUS_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=[
  'financeClientRow',
  'financeReconciliationStatusForScope',
  'financeReceivablesForClient',
  'financeReceivableGroupsForClient',
  'financePaidGroupsForClient',
  'financeClientCostGroups',
  'financeClientActiveMonths',
  'financeSettlementMonthMatch',
  'financeDefaultSettlementMonth',
  'defaultFinanceRebateForm',
];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
class FixedDate extends Date{
  constructor(...args){super(...(args.length?args:['2026-08-15T12:00:00Z']));}
}
const factory=`({
  financeReceivables:[], financeCosts:[], financeReconciliations:[], financeRebateChannelOptions:[],
  financePeriodMonths(){return ['2026-08','2026-09'];},
  financeSpendForChannelMonth(){return{};}, financeClientSpendForChannelMonth(){return{};},
  financeAdSpendGroups(){return{};}, isMonthLocked(){return false;}, financeReceivablePaid(){return 0;},
  financeDateMatch(){return true;}, financeCostAllocatedAmountForClient(){return 0;},
  clientContractOverlapsMonth(){return false;}, localDateKey(){return '2026-08-29';},
  ${names.map(name=>sources[name]).join(',\n  ')}
})`;
let subject;
try{subject=vm.runInNewContext(factory,{Number,String,Object,Array,Set,Map,Math,Date:FixedDate},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_FINANCE_CLIENT_STATUS_FAILED: unable to execute final implementations: ${error.message}`);}

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_CLIENT_STATUS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const near=(actual,expected,label)=>{if(Math.abs(Number(actual)-Number(expected))>1e-9)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const groupsEq=(actual,expected,label)=>{
  jsonEq(Object.keys(actual).sort(),Object.keys(expected).sort(),label+' currencies');
  for(const [currency,value] of Object.entries(expected))near(actual[currency],value,`${label} ${currency}`);
};

// Receivables stay client- and settlement-period-scoped, and currency/default-USD
// aggregation is numeric rather than string concatenation.
subject.financePeriodMonths=()=>['2026-08','2026-09'];
subject.financeReceivables=[
  {id:'a',clientId:'c1',settlementMonth:'2026-08',currency:'USD',amount:100,paid:120},
  {id:'b',clientId:'c1',settlementMonth:'2026-09',currency:'CNY',amount:'50',paid:30},
  {id:'c',clientId:'c1',settlementMonth:'2026-08',amount:25,paid:10},
  {id:'other-client',clientId:'c2',settlementMonth:'2026-08',currency:'USD',amount:999,paid:999},
  {id:'out-period',clientId:'c1',settlementMonth:'2026-10',currency:'USD',amount:999,paid:999},
];
const c1={id:'c1'};
jsonEq(subject.financeReceivablesForClient(null),[],'null client has no receivables');
jsonEq(subject.financeReceivablesForClient(c1).map(r=>r.id),['a','b','c'],'receivable client+period filter');
groupsEq(subject.financeReceivableGroupsForClient(c1),{USD:125,CNY:50},'receivable amount groups');
subject.financeReceivablePaid=row=>Number(row.paid||0);
groupsEq(subject.financePaidGroupsForClient(c1),{USD:110,CNY:30},'paid groups cap each row at receivable amount');

// Cost allocation only includes in-period costs with a material allocation for the
// requested client, preserving per-currency totals.
subject.financeCosts=[
  {id:'k1',date:'2026-08-03',currency:'USD',inPeriod:true,alloc:{c1:20}},
  {id:'k2',date:'2026-08-04',currency:'CNY',inPeriod:true,alloc:{c1:'7.5'}},
  {id:'k3',date:'2026-08-05',inPeriod:true,alloc:{c1:1e-8}},
  {id:'k4',date:'2026-07-31',currency:'USD',inPeriod:false,alloc:{c1:999}},
  {id:'k5',date:'2026-08-06',currency:'USD',inPeriod:true,alloc:{c2:999}},
];
subject.financeDateMatch=date=>subject.financeCosts.find(c=>c.date===date)?.inPeriod===true;
subject.financeCostAllocatedAmountForClient=(cost,client)=>Number(cost.alloc?.[client.id]||0);
groupsEq(subject.financeClientCostGroups(c1),{USD:20,CNY:7.5},'client cost allocation groups');

// Active months and settlement membership must be exact month-list filters.
subject.financePeriodMonths=()=>['2026-07','2026-08','2026-09'];
subject.clientContractOverlapsMonth=(client,month)=>(client.activeMonths||[]).includes(month);
jsonEq(subject.financeClientActiveMonths({id:'c1',activeMonths:['2026-07','2026-09']}),['2026-07','2026-09'],'client active month intersection');
eq(subject.financeSettlementMonthMatch('2026-08'),true,'settlement month included');
eq(subject.financeSettlementMonthMatch('2026-10'),false,'settlement month excluded');
eq(subject.financeSettlementMonthMatch(null),false,'blank settlement month excluded');

// Reconciliation completeness requires every positive channel/month/currency spend
// bucket to have a non-VOID entry and unassigned spend to stay within one-cent noise.
subject.financeRebateChannelOptions=[{providerId:'p1',contactId:'x'},{providerId:'p2',contactId:'y'}];
subject.financePeriodMonths=()=>['2026-08','2026-09'];
const totalSpend={
  'p1|x|2026-08':{USD:100,CNY:0},
  'p1|x|2026-09':{EUR:50},
  'p2|y|2026-08':{},
  'p2|y|2026-09':{CNY:20},
};
const clientSpend={'c1|p1|x|2026-08':{USD:10}};
let totalCalls=0,clientCalls=[];
subject.financeSpendForChannelMonth=(p,c,m)=>{totalCalls++;return totalSpend[`${p}|${c}|${m}`]||{};};
subject.financeClientSpendForChannelMonth=(client,p,c,m)=>{clientCalls.push([client,p,c,m]);return clientSpend[`${client}|${p}|${c}|${m}`]||{};};
subject._unassigned={USD:0.006,CNY:-0.003};
let adCalls=[];
subject.financeAdSpendGroups=(client,months,mode)=>{adCalls.push({client,months:[...months],mode});return subject._unassigned;};
subject._locked=new Set(['2026-08','2026-09']);
subject.isMonthLocked=month=>subject._locked.has(month);
subject.financeReconciliations=[
  {status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-08',currency:'USD'},
  {status:'VOID',providerId:'p1',contactId:'x',settlementMonth:'2026-09',currency:'EUR'},
  {status:'LOCKED',providerId:'p2',contactId:'y',settlementMonth:'2026-09',currency:'CNY'},
];
let status=subject.financeReconciliationStatusForScope();
eq(status.pendingReconciliations,1,'VOID does not satisfy positive spend reconciliation');
near(status.unassignedSpendTotal,0.009,'unassigned spend uses absolute currency totals');
eq(status.allLocked,true,'all selected months locked');
eq(status.complete,false,'missing reconciliation keeps scope incomplete');
subject.financeReconciliations.push({status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-09',currency:'EUR'});
status=subject.financeReconciliationStatusForScope();
eq(status.pendingReconciliations,0,'all positive channel buckets reconciled');
eq(status.complete,true,'one-cent-or-less unassigned noise still complete');
subject._unassigned={USD:0.011};
status=subject.financeReconciliationStatusForScope();
eq(status.complete,false,'unassigned spend above one cent blocks completeness');

// Client-scoped status must call the client spend path, not total channel spend, and
// pass the same client into the UNASSIGNED aggregation.
subject._unassigned={};
subject.financeReconciliations=[{status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-08',currency:'USD'}];
totalCalls=0;clientCalls=[];adCalls=[];
status=subject.financeReconciliationStatusForScope('c1',['2026-08']);
eq(status.pendingReconciliations,0,'client reconciliation complete');
eq(status.complete,true,'client complete with no unassigned spend');
eq(totalCalls,0,'client scope does not call total channel spend');
eq(clientCalls.length,2,'client scope evaluates every configured channel option');
jsonEq(clientCalls[0],['c1','p1','x','2026-08'],'client spend call identity');
jsonEq(adCalls[0],{client:'c1',months:['2026-08'],mode:'UNASSIGNED'},'client unassigned spend scope');
subject._locked=new Set();
status=subject.financeReconciliationStatusForScope('c1',['2026-08']);
eq(status.allLocked,false,'unlocked month reflected independently of completeness');

// Default settlement month chooses current month when available, otherwise the last
// selected month, and the rebate form receives that month plus safe defaults.
subject.financePeriodMonths=()=>['2026-07','2026-08'];
eq(subject.financeDefaultSettlementMonth(),'2026-08','default settlement uses current month when selected');
subject.financePeriodMonths=()=>['2026-06','2026-07'];
eq(subject.financeDefaultSettlementMonth(),'2026-07','default settlement falls back to last selected month');
subject.financePeriodMonths=()=>[];
eq(subject.financeDefaultSettlementMonth(),'2026-08','default settlement falls back to current month when no period months');
subject.financePeriodMonths=()=>['2026-07','2026-08'];
subject.localDateKey=()=> '2026-08-29';
jsonEq(subject.defaultFinanceRebateForm(),{id:null,channelKey:'',providerId:'',contactId:'',settlementMonth:'2026-08',currency:'USD',amount:'',confirmedDate:'2026-08-29',note:''},'default rebate form');

// Client-row composition must preserve deal/channel deduplication, service-fee-only
// subtotaling, expected-vs-actual net profit, reconciliation entry count, and the
// three user-visible rebate confirmation states.
const rowDeals=[
  {id:'d1',providerId:'p1',contactId:'x',providerName:'Provider A',contactName:'Alice'},
  {id:'d2',providerId:'p1',contactId:'x',providerName:'Provider A',contactName:'Alice'},
  {id:'d3',providerId:'p2',contactId:'y',providerName:'Provider B',contactName:'Bob'},
];
const receivableRows=[
  {incomeType:'SERVICE_FEE',currency:'USD',amount:100},
  {currency:'CNY',amount:'50'},
  {incomeType:'OTHER',currency:'USD',amount:25},
];
subject.financeDealsForClient=()=>rowDeals;
subject.financeDealsFinancials=()=>({rebateGroups:{USD:10}});
subject.financeClientAdSpendGroups=()=>({USD:500});
subject.financeReceivablesForClient=()=>receivableRows;
subject.financeReceivableGroupsForClient=()=>({USD:100,CNY:20});
subject.financePaidGroupsForClient=()=>({USD:80,CNY:5});
subject.financeActualRebateGroups=()=>({USD:5,CNY:2});
subject.financeClientCostGroups=()=>({USD:15});
subject.openingProviderName=deal=>deal.providerName;
subject.openingContactName=deal=>deal.contactName;
subject.financePeriodMonths=()=>['2026-08'];
subject.financeSettlementMonthMatch=month=>String(month)==='2026-08';
subject.financeActualRebateClientShare=entry=>Number(entry.share||0);
subject.financeClientActiveMonths=()=>['2026-07','2026-08'];
subject.financeProfitGroups=(service,rebate)=>{
  const out={...service};for(const [cur,val] of Object.entries(rebate||{}))out[cur]=(out[cur]||0)+Number(val||0);return out;
};
subject.subtractSpendGroups=(left,right)=>{
  const out={...left};for(const [cur,val] of Object.entries(right||{}))out[cur]=(out[cur]||0)-Number(val||0);return out;
};
subject.financeReconciliations=[
  {status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-08',share:4},
  {status:'LOCKED',providerId:'p2',contactId:'y',settlementMonth:'2026-08',share:2},
  {status:'VOID',providerId:'p1',contactId:'x',settlementMonth:'2026-08',share:99},
  {status:'CONFIRMED',providerId:'p1',contactId:'z',settlementMonth:'2026-08',share:99},
  {status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-09',share:99},
  {status:'CONFIRMED',providerId:'p1',contactId:'x',settlementMonth:'2026-08',share:0},
];
subject._rowStatus={complete:false,allLocked:false,pendingReconciliations:2};
subject.financeReconciliationStatusForScope=()=>subject._rowStatus;
let row=subject.financeClientRow(c1);
eq(row.receivableCount,3,'client row receivable count');
eq(row.activeMonths,2,'client row active month count');
groupsEq(row.receivableGroups,{USD:100,CNY:20},'client row receivables');
groupsEq(row.paidGroups,{USD:80,CNY:5},'client row paid');
groupsEq(row.serviceFeeGroups,{USD:100,CNY:50},'client row service-fee subtotal excludes non-service income');
groupsEq(row.expectedNetProfitGroups,{USD:95,CNY:20},'client row expected net profit');
groupsEq(row.actualNetProfitGroups,{USD:90,CNY:22},'client row actual net profit');
eq(row.channelLabels.length,2,'client row channel labels deduplicated');
eq(row.actualEntryCount,2,'client row actual entry count filters channel/month/status/share');
eq(row.actualProfitConfirmed,false,'pending rebate status not confirmed');
eq(row.actualProfitLabel,'待返点确认','pending rebate label');
eq(row.pendingRebateCount,2,'pending reconciliation count surfaced');
subject._rowStatus={complete:true,allLocked:false,pendingReconciliations:0};
row=subject.financeClientRow(c1);
eq(row.actualProfitConfirmed,true,'confirmed rebate status');
eq(row.actualProfitLabel,'已确认','confirmed rebate label');
subject._rowStatus={complete:true,allLocked:true,pendingReconciliations:0};
row=subject.financeClientRow(c1);
eq(row.actualProfitLabel,'已月结','locked confirmed rebate label');

console.log('BUSINESS_FINANCE_CLIENT_STATUS_OK: receivable+paid+cost+active-month+reconciliation+defaults+client-row-status=executed');
