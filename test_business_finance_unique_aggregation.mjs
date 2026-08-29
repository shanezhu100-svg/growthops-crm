import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_UNIQUE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_UNIQUE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_UNIQUE_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_UNIQUE_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=[
  'openingDealsSpendGroupsUniqueForPeriod','openingDealsRebateGroupsUniqueForPeriod','openingDealsSpendGroupsUnique','rebateGroups','openingProvidersRebateGroups','mergeSpendGroups','financeClientAdSpendGroups','financeUnassignedSpendGroupsForMonth','financeDealsForClient','financeChannelDeals',
];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const factory=`({
  openingDeals:[], openingSpendPeriod:'2026-08', openingProviderFilter:'ALL',
  _financialCalls:[], _adSpendCalls:[],
  openingDealsFinancialsForPeriod(deals,period){this._financialCalls.push({deals,period});return{spendGroups:{USD:123,CNY:456},rebateGroups:{USD:7,CNY:8}};},
  financePeriodMonths(){return ['2026-08','2026-09'];},
  financeAdSpendGroups(clientId,months,mode){this._adSpendCalls.push({clientId,months,mode});return{USD:99};},
  openingDealOverlapsFinancePeriod(deal){return deal?.overlaps===true;},
  ${names.map(name=>sources[name]).join(',\n  ')}
})`;
let subject;
try{subject=vm.runInNewContext(factory,{Number,String,Object,Array},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_FINANCE_UNIQUE_FAILED: unable to execute final implementations: ${error.message}`);}

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_UNIQUE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};

const deals=[{id:'a'},{id:'b'}];
jsonEq(subject.openingDealsSpendGroupsUniqueForPeriod(deals,'2026-07'),{USD:123,CNY:456},'unique spend delegates to combined financials');
eq(subject._financialCalls.length,1,'unique spend calls combined financials exactly once');
eq(subject._financialCalls[0].deals,deals,'unique spend preserves deal collection identity');
eq(subject._financialCalls[0].period,'2026-07','unique spend preserves requested period');
subject._financialCalls.length=0;
jsonEq(subject.openingDealsRebateGroupsUniqueForPeriod(deals,'2026-06'),{USD:7,CNY:8},'unique rebate delegates to combined financials');
eq(subject._financialCalls.length,1,'unique rebate calls combined financials exactly once');
eq(subject._financialCalls[0].period,'2026-06','unique rebate preserves requested period');
subject._financialCalls.length=0;
jsonEq(subject.openingDealsSpendGroupsUnique(deals),{USD:123,CNY:456},'default unique spend delegates using opening period');
eq(subject._financialCalls.length,1,'default unique spend single delegation');
eq(subject._financialCalls[0].period,'2026-08','default unique spend uses current opening period');

jsonEq(subject.rebateGroups({USD:200,CNY:'700'},5),{USD:10,CNY:35},'rebateGroups computes each currency independently');
const mergeTarget={USD:10};
eq(subject.mergeSpendGroups(mergeTarget,{USD:'2.5',CNY:7}),mergeTarget,'mergeSpendGroups mutates/returns target authority');
jsonEq(mergeTarget,{USD:12.5,CNY:7},'mergeSpendGroups sums currencies without cross-currency conversion');

subject.openingDeals=[{id:'p1-a',providerId:'p1'},{id:'p2-a',providerId:'p2'},{id:'p1-b',providerId:'p1'}];
subject._financialCalls.length=0;
subject.openingProvidersRebateGroups('2026-05','p1');
eq(subject._financialCalls.length,1,'provider rebate uses one unique financial aggregation');
jsonEq(subject._financialCalls[0].deals.map(d=>d.id),['p1-a','p1-b'],'provider filter includes only matching provider deals');
eq(subject._financialCalls[0].period,'2026-05','provider aggregate preserves period');
subject._financialCalls.length=0;
subject.openingProvidersRebateGroups('2026-04','ALL');
jsonEq(subject._financialCalls[0].deals.map(d=>d.id),['p1-a','p2-a','p1-b'],'ALL provider filter preserves all deals');

subject._adSpendCalls.length=0;
jsonEq(subject.financeClientAdSpendGroups({id:'client-1'},['2026-01']),{USD:99},'client ad-spend wrapper returns delegated groups');
jsonEq(subject._adSpendCalls[0],{clientId:'client-1',months:['2026-01'],mode:'ALL'},'client ad-spend wrapper arguments');
subject._adSpendCalls.length=0;
subject.financeClientAdSpendGroups({id:'client-2'});
jsonEq(subject._adSpendCalls[0],{clientId:'client-2',months:['2026-08','2026-09'],mode:'ALL'},'client ad-spend default months');
subject._adSpendCalls.length=0;
subject.financeUnassignedSpendGroupsForMonth('2026-03');
jsonEq(subject._adSpendCalls[0],{clientId:null,months:['2026-03'],mode:'UNASSIGNED'},'unassigned month wrapper arguments');

subject.openingDeals=[
  {id:'ok',status:'OPENED',clientId:'c1',providerId:'p1',contactId:'x',overlaps:true},
  {id:'wrong-client',status:'OPENED',clientId:'c2',providerId:'p1',contactId:'x',overlaps:true},
  {id:'closed',status:'CLOSED',clientId:'c1',providerId:'p1',contactId:'x',overlaps:true},
  {id:'no-overlap',status:'OPENED',clientId:'c1',providerId:'p1',contactId:'x',overlaps:false},
  {id:'other-contact',status:'OPENED',clientId:'c1',providerId:'p1',contactId:'y',overlaps:true},
  {id:'other-provider',status:'OPENED',clientId:'c1',providerId:'p2',contactId:'x',overlaps:true},
];
jsonEq(subject.financeDealsForClient({id:'c1'}).map(d=>d.id),['ok','other-contact','other-provider'],'finance client deals require opened+client+overlap');
jsonEq(subject.financeChannelDeals('p1','x').map(d=>d.id),['ok','wrong-client','no-overlap'],'channel deals filter status/provider/contact but not period overlap');
jsonEq(subject.financeChannelDeals('p1','x','c1').map(d=>d.id),['ok','no-overlap'],'optional channel client filter isolates client');

console.log('BUSINESS_FINANCE_UNIQUE_OK: combined-aggregation+currency-isolation+provider-filter+client-wrappers+deal-selection=executed');
await import('./test_business_finance_settlement.mjs');
await import('./test_business_finance_client_status.mjs');
