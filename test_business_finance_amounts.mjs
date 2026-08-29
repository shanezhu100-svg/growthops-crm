import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_AMOUNTS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_AMOUNTS_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_AMOUNTS_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const definitions=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(definitions.length<2||definitions[0][1]!==name)throw new Error(`BUSINESS_FINANCE_AMOUNTS_FAILED: ${name} method-boundary parser drifted`);
  const nextStart=definitions[1].index+definitions[1][0].indexOf(definitions[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const spendForPeriodSource=extractMethod('openingDealSpendGroupsForPeriod');
const financialsForPeriodSource=extractMethod('openingDealsFinancialsForPeriod');
const financeAdSpendSource=extractMethod('financeAdSpendGroups');
const receivableSource=extractMethod('financeReceivableGroupsForClientMonth');
const serviceFeeReceivableSource=extractMethod('financeServiceFeeReceivableGroupsForClientMonth');
const financeDealsFinancialsSource=extractMethod('financeDealsFinancials');

const factorySource=`({
  clients:[], financeReceivables:[],
  financePeriodMonths(){return ['2026-08'];},
  openingDealMatchedAccounts(deal){return deal?.accounts||[];},
  openingPeriodMatchFor(date,period){return period==='ALL'||String(date||'').slice(0,7)===String(period);},
  openingDealOwnsRecord(deal,account,date){return String(account?.ownerDealId||'')===String(deal?.id||'');},
  openingDealRebateRate(deal,date){return Number(deal?.rebateRate||0);},
  accountRebateMode(account){return account?.rebateMode||'NONE';},
  openingDealOwnerForRecord(clientId,platform,account,date){return account?.ownerDealId?{id:account.ownerDealId}:null;},
  financeDateMatch(date){return String(date||'').slice(0,7)==='2026-08';},
  ${spendForPeriodSource},
  ${financialsForPeriodSource},
  ${financeAdSpendSource},
  ${receivableSource},
  ${serviceFeeReceivableSource},
  ${financeDealsFinancialsSource}
})`;
let subject;
try{subject=vm.runInNewContext(factorySource,{Number,String,Array,Set,Object,Math},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_FINANCE_AMOUNTS_FAILED: unable to execute final finance implementations: ${error.message}`);}

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_AMOUNTS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const assertNear=(actual,expected,label)=>{if(Math.abs(Number(actual)-Number(expected))>1e-9)fail(label,expected,actual);};
const assertGroups=(actual,expected,label)=>{
  const actualKeys=Object.keys(actual).sort();
  const expectedKeys=Object.keys(expected).sort();
  if(JSON.stringify(actualKeys)!==JSON.stringify(expectedKeys))fail(label+' currencies',JSON.stringify(expectedKeys),JSON.stringify(actualKeys));
  for(const key of expectedKeys)assertNear(actual[key],expected[key],`${label} ${key}`);
};

const acctA={ownerDealId:'deal-a',adSpendCurrency:'USD',adDataRecords:[
  {date:'2026-08-01',currency:'USD',spend:100},
  {date:'2026-08-02',currency:'CNY',spend:700},
  {date:'2026-09-01',currency:'USD',spend:50},
]};
const acctB={ownerDealId:'deal-b',adSpendCurrency:'EUR',adDataRecords:[{date:'2026-08-03',spend:'80'}]};
const dealA={id:'deal-a',rebateRate:5,accounts:[acctA,acctB]};
const dealB={id:'deal-b',rebateRate:8,accounts:[acctB]};
assertGroups(subject.openingDealSpendGroupsForPeriod(dealA,'2026-08'),{USD:100,CNY:700},'owned period spend');
assertGroups(subject.openingDealSpendGroupsForPeriod(dealA,'2026-09'),{USD:50},'period filter');
const periodFinancials=subject.openingDealsFinancialsForPeriod([dealA,dealB],'2026-08');
assertGroups(periodFinancials.spendGroups,{USD:100,CNY:700,EUR:80},'period financial spend');
assertGroups(periodFinancials.rebateGroups,{USD:5,CNY:35,EUR:6.4},'period rebate amount');
const financeFinancials=subject.financeDealsFinancials([dealA,dealB]);
assertGroups(financeFinancials.spendGroups,{USD:100,CNY:700,EUR:80},'finance-period spend');
assertGroups(financeFinancials.rebateGroups,{USD:5,CNY:35,EUR:6.4},'finance-period rebate');

const attributed={rebateMode:'CHANNEL',ownerDealId:'deal-a',adSpendCurrency:'USD',adDataRecords:[{date:'2026-08-04',spend:100},{date:'2026-09-04',spend:20}]};
const unassigned={rebateMode:'CHANNEL',adSpendCurrency:'USD',adDataRecords:[{date:'2026-08-05',spend:50}]};
const noRebate={rebateMode:'NONE',adSpendCurrency:'CNY',adDataRecords:[{date:'2026-08-06',spend:300}]};
subject.clients=[
  {id:'client-1',fbAccounts:[attributed,unassigned],tkAccounts:[noRebate]},
  {id:'client-2',fbAccounts:[{rebateMode:'NONE',adSpendCurrency:'USD',adDataRecords:[{date:'2026-08-07',spend:999}]}],tkAccounts:[]},
];
assertGroups(subject.financeAdSpendGroups('client-1',null,'ALL'),{USD:150,CNY:300},'all client spend');
assertGroups(subject.financeAdSpendGroups('client-1',['2026-08'],'ATTRIBUTED'),{USD:100},'attributed channel spend');
assertGroups(subject.financeAdSpendGroups('client-1',['2026-08'],'UNASSIGNED'),{USD:50},'unassigned channel spend');
assertGroups(subject.financeAdSpendGroups('client-1',['2026-08'],'NO_REBATE'),{CNY:300},'no-rebate spend');
assertGroups(subject.financeAdSpendGroups('client-2',['2026-08'],'ALL'),{USD:999},'client filter isolation');

subject.financeReceivables=[
  {clientId:'client-1',settlementMonth:'2026-08',currency:'USD',amount:100},
  {clientId:'client-1',settlementMonth:'2026-08',currency:'USD',amount:'50',incomeType:'OTHER'},
  {clientId:'client-1',settlementMonth:'2026-08',currency:'CNY',amount:700,incomeType:'SERVICE_FEE'},
  {clientId:'client-1',settlementMonth:'2026-08',amount:25,incomeType:'SERVICE_FEE'},
  {clientId:'client-1',settlementMonth:'2026-09',currency:'USD',amount:200},
  {clientId:'client-2',settlementMonth:'2026-08',currency:'USD',amount:300},
];
const client1={id:'client-1'};
assertGroups(subject.financeReceivableGroupsForClientMonth(client1,'2026-08'),{USD:175,CNY:700},'all receivables');
assertGroups(subject.financeServiceFeeReceivableGroupsForClientMonth(client1,'2026-08'),{USD:125,CNY:700},'service-fee receivables');
assertGroups(subject.financeReceivableGroupsForClientMonth(client1,'2026-09'),{USD:200},'receivable month isolation');
assertGroups(subject.financeReceivableGroupsForClientMonth({id:'client-2'},'2026-08'),{USD:300},'receivable client isolation');

console.log('BUSINESS_FINANCE_AMOUNTS_OK: owned-spend+rebate-arithmetic+currency-isolation+attribution-modes+receivable-grouping=executed');
await import('./test_business_finance_unique_aggregation.mjs');
