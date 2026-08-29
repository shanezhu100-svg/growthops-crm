import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);if(!match)throw new Error(`BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]),tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);return tail.slice(0,next).replace(/,\s*$/,'').trim();
}
const names=[
 'financeReconciliationRows','financeVisibleReconciliationHistory','financeCompanyNonClientCostGroups','financeCompanyProjectCostGroups',
 'financeCompanyPublicCostGroups','financePublicCostDisplayGroups','financeCompanyPublicCostText','financeDirectClientCostGroups',
 'financeDirectClientCostGroupsForMonth','financeDirectClientCostText','financeClientCostGroupsForMonth','financeAttributedSpendGroups','financeAttributedSpendText'
];
const methods={};for(const name of names){const obj=vm.runInNewContext(`({${extractMethod(name)}})`,{Number,String,Object,Array,Math,Set,Map},{timeout:1000});methods[name]=obj[name];}
const call=(name,subject,...args)=>methods[name].call(subject,...args);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const merge=(target,source)=>{for(const [k,v] of Object.entries(source||{}))target[k]=(target[k]||0)+Number(v||0);return target;};
const subtract=(left,right)=>{const out={};for(const key of new Set([...Object.keys(left||{}),...Object.keys(right||{})]))out[key]=Number(left?.[key]||0)-Number(right?.[key]||0);return out;};

let snapshotRows=[
 {id:'pending-sep',providerId:'p2',providerName:'B',month:'2026-09',record:null},
 {id:'confirmed-sep',providerId:'p1',providerName:'A',month:'2026-09',record:{status:'CONFIRMED'}},
 {id:'void-aug',providerId:'p1',providerName:'A',month:'2026-08',record:{status:'VOID'}},
];
let subject={financeActivePeriodSnapshot:{reconciliations:snapshotRows},financeProviderFilter:'ALL',financeReconciliationStatusFilter:'ALL'};
jsonEq(call('financeReconciliationRows',subject).map(row=>row.id),['confirmed-sep','pending-sep','void-aug'],'snapshot reconciliation sorts newest month first then provider name');
subject.financeReconciliationStatusFilter='PENDING';jsonEq(call('financeReconciliationRows',subject).map(row=>row.id),['pending-sep'],'PENDING selects rows without record');
subject.financeReconciliationStatusFilter='CONFIRMED';jsonEq(call('financeReconciliationRows',subject).map(row=>row.id),['confirmed-sep'],'CONFIRMED selects non-VOID records');
subject.financeReconciliationStatusFilter='VOID';jsonEq(call('financeReconciliationRows',subject).map(row=>row.id),['void-aug'],'VOID selects VOID records');
subject.financeReconciliationStatusFilter='ALL';subject.financeProviderFilter='p1';jsonEq(call('financeReconciliationRows',subject).map(row=>row.id),['confirmed-sep','void-aug'],'snapshot provider filter uses normalized provider id');

const liveRecords=[
 {providerId:'p1',contactId:'c1',settlementMonth:'2026-09',currency:'USD',confirmedSpend:110,status:'CONFIRMED'},
 {providerId:'p1',contactId:'c1',settlementMonth:'2026-08',currency:'CNY',confirmedSpend:40,status:'VOID'},
];
subject={
 financeActivePeriodSnapshot:null,financeReconciliations:liveRecords,financeProviderFilter:'ALL',financeReconciliationStatusFilter:'ALL',
 financeRebateChannelOptions:[{providerId:'p1',contactId:'c1',provider:{name:'Provider A'},contact:{name:'Contact A'}}],
 financePeriodMonths(){return ['2026-09','2026-08'];},
 financeChannelMonthGroups(providerId,contactId,month){return month==='2026-09'?{USD:100}:month==='2026-08'?{CNY:50}:{};},
 financeExpectedRebateForChannelMonth(providerId,contactId,month){return month==='2026-09'?{USD:10,EUR:5}:{};},
};
let rows=call('financeReconciliationRows',subject);
jsonEq(rows.map(row=>row.key),['p1|c1|2026-09|USD','p1|c1|2026-09|EUR','p1|c1|2026-08|CNY'],'live reconciliation builds currency union per channel/month and sorts by month');
let usd=rows[0];eq(usd.systemSpend,100,'live reconciliation system spend');eq(usd.expectedRebate,10,'live reconciliation expected rebate');eq(usd.spendDiff,10,'live reconciliation spend difference uses confirmed minus system');
eq(rows[1].record,null,'currency without reconciliation remains pending');eq(rows[1].expectedRebate,5,'expected-only currency is retained');eq(rows[2].record.status,'VOID','record-only/VOID currency is retained');eq(rows[2].spendDiff,-10,'VOID row still calculates spend difference');
subject.financeReconciliationStatusFilter='PENDING';jsonEq(call('financeReconciliationRows',subject).map(row=>row.key),['p1|c1|2026-09|EUR'],'live PENDING filter');
subject.financeReconciliationStatusFilter='CONFIRMED';jsonEq(call('financeReconciliationRows',subject).map(row=>row.key),['p1|c1|2026-09|USD'],'live CONFIRMED excludes VOID');
subject.financeReconciliationStatusFilter='VOID';jsonEq(call('financeReconciliationRows',subject).map(row=>row.key),['p1|c1|2026-08|CNY'],'live VOID filter');
subject.financeReconciliationStatusFilter='ALL';subject.financeProviderFilter='other';jsonEq(call('financeReconciliationRows',subject),[],'live provider filter can exclude entire provider');

subject={financeReconciliations:[
 {id:'sep-old',settlementMonth:'2026-09',providerId:'p1',confirmedDate:'2026-09-02'},
 {id:'sep-new',settlementMonth:'2026-09',providerId:'p1',confirmedDate:'2026-09-10'},
 {id:'aug',settlementMonth:'2026-08',providerId:'p1',confirmedDate:'2026-08-20'},
 {id:'other-provider',settlementMonth:'2026-09',providerId:'p2',confirmedDate:'2026-09-30'},
 {id:'out-period',settlementMonth:'2026-10',providerId:'p1',confirmedDate:'2026-10-01'},
],financeProviderFilter:'p1',financeSettlementMonthMatch(month){return ['2026-08','2026-09'].includes(String(month));}};
jsonEq(call('financeVisibleReconciliationHistory',subject).map(row=>row.id),['sep-new','sep-old','aug'],'visible reconciliation history filters period/provider and sorts month then confirmed date descending');
subject.financeProviderFilter='ALL';jsonEq(call('financeVisibleReconciliationHistory',subject).map(row=>row.id),['other-provider','sep-new','sep-old','aug'],'history ALL provider includes every in-period provider');

const costs=[
 {id:'project-usd',date:'2026-09-01',scope:'COMPANY_PROJECT',amount:10,currency:'USD'},
 {id:'project-default',date:'2026-09-02',scope:'COMPANY_PROJECT',amount:2},
 {id:'company-cny',date:'2026-09-03',scope:'COMPANY',amount:20,currency:'CNY'},
 {id:'allocate-service',date:'2026-09-04',scope:'ALLOCATE_SERVICE',amount:30,currency:'USD'},
 {id:'allocate-spend',date:'2026-09-05',scope:'ALLOCATE_SPEND',amount:5},
 {id:'client-c1',date:'2026-09-06',scope:'CLIENT',clientId:'c1',amount:12,currency:'USD'},
 {id:'client-c2',date:'2026-09-07',scope:'CLIENT',clientId:2,amount:3,currency:'CNY'},
 {id:'legacy-client',date:'2026-08-08',clientId:'c1',amount:4,currency:'USD'},
 {id:'out-date',date:'2026-10-01',scope:'COMPANY_PROJECT',amount:999,currency:'USD'},
];
subject={financeActivePeriodSnapshot:null,financeCosts:costs,financeDateMatch(date){return /^2026-(08|09)-/.test(String(date));}};
jsonEq(call('financeCompanyProjectCostGroups',subject),{USD:12},'company project groups include only in-period COMPANY_PROJECT and default currency USD');
jsonEq(call('financeCompanyPublicCostGroups',subject),{CNY:20,USD:35},'company public groups include COMPANY and shared allocation scopes but exclude project/client');
subject.financeActivePeriodSnapshot={company:{companyProjectCostGroups:{EUR:7},companyPublicCostGroups:{JPY:9}}};const projectSnap=call('financeCompanyProjectCostGroups',subject),publicSnap=call('financeCompanyPublicCostGroups',subject);jsonEq(projectSnap,{EUR:7},'company project snapshot override');jsonEq(publicSnap,{JPY:9},'company public snapshot override');if(projectSnap===subject.financeActivePeriodSnapshot.company.companyProjectCostGroups||publicSnap===subject.financeActivePeriodSnapshot.company.companyPublicCostGroups)throw new Error('BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: company snapshot groups must be defensive copies');
subject={financeCompanyProjectCostGroups:{USD:12,CNY:1},financeCompanyPublicCostGroups:{USD:35,CNY:20},mergeSpendGroups:merge};jsonEq(call('financeCompanyNonClientCostGroups',subject),{USD:47,CNY:21},'non-client company cost merges project and public groups');
subject={financeClientFilter:'ALL',financeCompanyNonClientCostGroups:{USD:47},financeCostGroups:{USD:100},financeDirectClientCostGroups:{USD:12},subtractSpendGroups:subtract};jsonEq(call('financePublicCostDisplayGroups',subject),{USD:47},'ALL client filter displays non-client company cost');subject.financeClientFilter='c1';jsonEq(call('financePublicCostDisplayGroups',subject),{USD:88},'single-client public display subtracts direct-client cost from scoped total cost');
subject={financeCompanyPublicCostGroups:{USD:35,CNY:20},spendGroupsText(groups){return Object.entries(groups).map(([k,v])=>`${k}:${v}`).join('|');}};eq(call('financeCompanyPublicCostText',subject),'USD:35|CNY:20','company public cost text delegates grouped formatter');

subject={financeActiveSnapshotScope:null,financeCosts:costs,financeClientFilter:'ALL',financeDateMatch(date){return /^2026-(08|09)-/.test(String(date));}};
jsonEq(call('financeDirectClientCostGroups',subject),{USD:16,CNY:3},'direct client groups include CLIENT scope and legacy clientId across visible period');
subject.financeClientFilter='c1';jsonEq(call('financeDirectClientCostGroups',subject),{USD:16},'direct client groups respect selected client with normalized ids');subject.financeClientFilter='2';jsonEq(call('financeDirectClientCostGroups',subject),{CNY:3},'direct client groups match numeric client id through string normalization');
subject.financeActiveSnapshotScope={directClientCostGroups:{EUR:8}};const directSnap=call('financeDirectClientCostGroups',subject);jsonEq(directSnap,{EUR:8},'direct client snapshot override');if(directSnap===subject.financeActiveSnapshotScope.directClientCostGroups)throw new Error('BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: direct client snapshot must be copied');
subject={financeCosts:costs};jsonEq(call('financeDirectClientCostGroupsForMonth',subject,'2026-09'),{USD:12,CNY:3},'monthly direct client groups include all CLIENT costs in month');jsonEq(call('financeDirectClientCostGroupsForMonth',subject,'2026-09','c1'),{USD:12},'monthly direct client groups can restrict client');jsonEq(call('financeDirectClientCostGroupsForMonth',subject,'2026-08','c1'),{USD:4},'monthly direct client groups treat legacy clientId as CLIENT scope');
subject={financeDirectClientCostGroups:{USD:16},spendGroupsText(groups){return `direct:${groups.USD}`;}};eq(call('financeDirectClientCostText',subject),'direct:16','direct client cost text delegates grouped formatter');

subject={financeCosts:[
 {date:'2026-09-01',currency:'USD',allocations:{c1:5}},
 {date:'2026-09-02',currency:'CNY',allocations:{c1:-2}},
 {date:'2026-09-03',allocations:{c1:0.0000001}},
 {date:'2026-08-31',currency:'USD',allocations:{c1:99}},
],financeCostAllocatedAmountForClient(cost,client){return Number(cost.allocations?.[String(client.id)]||0);}};
jsonEq(call('financeClientCostGroupsForMonth',subject,{id:'c1'},'2026-09'),{USD:5,CNY:-2},'client monthly allocated cost filters month and ignores sub-threshold allocations');

let captured=null;subject={financeActiveSnapshotScope:{attributedSpendGroups:{USD:6}},financeClientFilter:'ALL',financePeriodMonths(){return ['2026-09'];},financeAdSpendGroups(){throw new Error('snapshot attributed spend must not call live aggregation');}};const attributedSnap=call('financeAttributedSpendGroups',subject);jsonEq(attributedSnap,{USD:6},'attributed spend snapshot override');if(attributedSnap===subject.financeActiveSnapshotScope.attributedSpendGroups)throw new Error('BUSINESS_FINANCE_RECONCILIATION_COST_FAILED: attributed snapshot must be copied');
subject={financeActiveSnapshotScope:null,financeClientFilter:'ALL',financePeriodMonths(){return ['2026-08','2026-09'];},financeAdSpendGroups(client,months,mode){captured=[client,months,mode];return {USD:11};}};jsonEq(call('financeAttributedSpendGroups',subject),{USD:11},'ALL attributed spend delegates live aggregation');jsonEq(captured,[null,['2026-08','2026-09'],'ATTRIBUTED'],'ALL attributed spend passes null client and ATTRIBUTED mode');subject.financeClientFilter='c9';call('financeAttributedSpendGroups',subject);jsonEq(captured,['c9',['2026-08','2026-09'],'ATTRIBUTED'],'client attributed spend passes selected client');subject.financeAttributedSpendGroups={USD:11};subject.spendGroupsText=groups=>`attributed:${groups.USD}`;eq(call('financeAttributedSpendText',subject),'attributed:11','attributed spend text delegates grouped formatter');

console.log('BUSINESS_FINANCE_RECONCILIATION_COST_OK: snapshot+live-reconciliation+history+company-cost+direct-cost+allocation+attributed-spend=executed');
