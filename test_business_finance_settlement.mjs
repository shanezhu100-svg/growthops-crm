import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_SETTLEMENT_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_SETTLEMENT_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=[
  'financeChannelMonthGroups',
  'financeExpectedRebateForChannelMonth',
  'financeClientExpectedRebateForChannelMonth',
  'financeSpendForChannelMonth',
  'financeClientSpendForChannelMonth',
  'financeActualRebateClientShare',
  'financeActualRebateGroups',
  'financeProfitGroups',
  'normalizeFinanceActualRebates',
  'financeEntryProviderName',
  'financeEntryContactName',
  'financeEntryLinkedClientCount',
];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const factory=`({
  openingDeals:[], openingProviders:[], financeReconciliations:[],
  _channelDeals:[], _expectedByClient:new Map(), _expectedTotal:{}, _spendByClient:new Map(), _spendTotal:{},
  financeChannelDeals(providerId,contactId,clientId=null){
    return this._channelDeals.filter(d=>String(d.providerId)===String(providerId)&&String(d.contactId||'')===String(contactId||'')&&(clientId===null||String(d.clientId)===String(clientId)));
  },
  openingDealMatchedAccounts(deal){return deal?.accounts||[];},
  openingDealOwnsRecord(deal,account,date){return String(account?.ownerDealId||'')===String(deal?.id||'');},
  openingDealRebateRate(deal,date){return Number(deal?.rateByDate?.[date]??deal?.rebateRate??0);},
  financeSettlementMonthMatch(month){return String(month)==='2026-08';},
  mergeSpendGroups(target,source){Object.entries(source||{}).forEach(([cur,val])=>target[cur]=(target[cur]||0)+Number(val||0));return target;},
  ${names.map(name=>sources[name]).join(',\n  ')}
})`;
let subject;
try{subject=vm.runInNewContext(factory,{Number,String,Object,Array,Set,Map},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_FINANCE_SETTLEMENT_FAILED: unable to execute final implementations: ${error.message}`);}

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_SETTLEMENT_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const near=(actual,expected,label)=>{if(Math.abs(Number(actual)-Number(expected))>1e-9)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const groupsEq=(actual,expected,label)=>{
  const ak=Object.keys(actual).sort(),ek=Object.keys(expected).sort();
  jsonEq(ak,ek,label+' currencies');
  for(const key of ek)near(actual[key],expected[key],`${label} ${key}`);
};

// Channel month aggregation must keep provider/contact/client, ownership, month,
// currency and date-effective rebate rate boundaries intact.
const a1={ownerDealId:'d1',adSpendCurrency:'USD',adDataRecords:[
  {date:'2026-08-01',spend:100,currency:'USD'},
  {date:'2026-08-02',spend:200,currency:'CNY'},
  {date:'2026-09-01',spend:50,currency:'USD'},
]};
const a2={ownerDealId:'d2',adSpendCurrency:'EUR',adDataRecords:[{date:'2026-08-03',spend:'80'}]};
subject._channelDeals=[
  {id:'d1',clientId:'c1',providerId:'p1',contactId:'x',rebateRate:5,rateByDate:{'2026-08-02':10},accounts:[a1,a2]},
  {id:'d2',clientId:'c2',providerId:'p1',contactId:'x',rebateRate:8,accounts:[a2]},
  {id:'d3',clientId:'c1',providerId:'p2',contactId:'x',rebateRate:99,accounts:[{ownerDealId:'d3',adDataRecords:[{date:'2026-08-01',spend:999,currency:'USD'}]}]},
];
groupsEq(subject.financeChannelMonthGroups('p1','x','2026-08',null,'SPEND'),{USD:100,CNY:200,EUR:80},'channel month spend');
groupsEq(subject.financeChannelMonthGroups('p1','x','2026-08',null,'REBATE'),{USD:5,CNY:20,EUR:6.4},'channel month expected rebate');
groupsEq(subject.financeChannelMonthGroups('p1','x','2026-08','c1','SPEND'),{USD:100,CNY:200},'client channel spend isolation');
groupsEq(subject.financeChannelMonthGroups('p1','x','2026-08','c1','REBATE'),{USD:5,CNY:20},'client channel rebate isolation');
groupsEq(subject.financeChannelMonthGroups('p1','x','2026-09',null,'SPEND'),{USD:50},'settlement month isolation');
groupsEq(subject.financeExpectedRebateForChannelMonth('p1','x','2026-08'),{USD:5,CNY:20,EUR:6.4},'expected rebate wrapper');
groupsEq(subject.financeClientExpectedRebateForChannelMonth('c2','p1','x','2026-08'),{EUR:6.4},'client expected rebate wrapper');
groupsEq(subject.financeSpendForChannelMonth('p1','x','2026-08'),{USD:100,CNY:200,EUR:80},'channel spend wrapper');
groupsEq(subject.financeClientSpendForChannelMonth('c2','p1','x','2026-08'),{EUR:80},'client spend wrapper');

// Actual rebate share prefers expected-rebate weights. A zero expected basis must
// fall back to spend weights; if neither basis exists, nothing is allocated.
subject.financeClientExpectedRebateForChannelMonth=(clientId)=>clientId==='c1'?{USD:30}:{USD:70};
subject.financeExpectedRebateForChannelMonth=()=>({USD:100});
subject.financeClientSpendForChannelMonth=(clientId)=>clientId==='c1'?{USD:200}:{USD:800};
subject.financeSpendForChannelMonth=()=>({USD:1000});
near(subject.financeActualRebateClientShare({currency:'USD',settlementMonth:'2026-08',providerId:'p1',contactId:'x',actualRebate:500},{id:'c1'}),150,'expected-rebate weighted actual share');
near(subject.financeActualRebateClientShare({currency:'USD',settlementMonth:'2026-08',providerId:'p1',contactId:'x',amount:500},{id:'c2'}),350,'amount fallback field with expected-rebate weighting');
subject.financeExpectedRebateForChannelMonth=()=>({USD:0});
subject.financeClientExpectedRebateForChannelMonth=()=>({USD:0});
near(subject.financeActualRebateClientShare({currency:'USD',settlementMonth:'2026-08',providerId:'p1',actualRebate:500},{id:'c1'}),100,'spend-weight fallback actual share');
subject.financeSpendForChannelMonth=()=>({USD:0});
near(subject.financeActualRebateClientShare({currency:'USD',settlementMonth:'2026-08',providerId:'p1',actualRebate:500},{id:'c1'}),0,'zero basis allocates nothing');

// Actual reconciliation aggregation excludes VOID/out-of-period/non-positive shares
// and keeps currencies isolated.
subject.financeActualRebateClientShare=(entry)=>Number(entry.syntheticShare||0);
subject.financeReconciliations=[
  {status:'CONFIRMED',settlementMonth:'2026-08',currency:'USD',syntheticShare:20},
  {status:'LOCKED',settlementMonth:'2026-08',currency:'USD',syntheticShare:5},
  {status:'CONFIRMED',settlementMonth:'2026-08',currency:'CNY',syntheticShare:70},
  {status:'VOID',settlementMonth:'2026-08',currency:'USD',syntheticShare:999},
  {status:'CONFIRMED',settlementMonth:'2026-09',currency:'USD',syntheticShare:999},
  {status:'CONFIRMED',settlementMonth:'2026-08',currency:'USD',syntheticShare:0},
];
groupsEq(subject.financeActualRebateGroups({id:'c1'}),{USD:25,CNY:70},'actual rebate reconciliation groups');
groupsEq(subject.financeProfitGroups({USD:100,CNY:7},{USD:20,EUR:5}),{USD:120,CNY:7,EUR:5},'profit merges service and rebate per currency');

// Historical actual-rebate normalization groups by channel/month/currency, sums
// amounts, merges notes, keeps newest confirmation/update dates, defaults USD, and
// resolves missing contact from matching historical deal metadata.
subject.openingDeals=[
  {clientId:'c1',providerId:'p1',platform:'FB',contactId:'contact-a'},
  {clientId:'c2',providerId:'p2',platform:'TK',contactId:'contact-b'},
];
const normalized=subject.normalizeFinanceActualRebates([
  {id:'r1',providerId:'p1',contactId:'contact-a',settlementMonth:'2026-08',currency:'USD',amount:10,note:'A',confirmedDate:'2026-08-10',updatedAt:'2026-08-11'},
  {id:'r2',providerId:'p1',contactId:'contact-a',settlementMonth:'2026-08',currency:'USD',amount:'5',note:'B',confirmedDate:'2026-08-12',updatedAt:'2026-08-09'},
  {id:'r3',providerId:'p1',clientId:'c1',platform:'FB',settlementMonth:'2026-08',amount:2,note:'C',confirmedDate:'2026-08-08',updatedAt:'2026-08-15'},
  {providerId:'p2',clientId:'c2',platform:'TK',settlementMonth:'2026-09',currency:'CNY',amount:30},
  {providerId:'',settlementMonth:'2026-08',amount:999},
  {providerId:'p1',settlementMonth:'',amount:999},
]);
eq(normalized.length,2,'normalization group/skip count');
const usd=normalized.find(r=>r.providerId==='p1');
near(usd.amount,17,'normalized grouped amount');
eq(usd.contactId,'contact-a','missing contact resolved from matching deal');
eq(usd.currency,'USD','normalized default currency');
eq(usd.note,'A；B；C','normalized notes preserve contributing notes');
eq(usd.confirmedDate,'2026-08-12','normalized latest confirmed date');
eq(usd.updatedAt,'2026-08-15','normalized latest updated timestamp');
const cny=normalized.find(r=>r.providerId==='p2');
eq(cny.contactId,'contact-b','platform-specific legacy contact resolution');
eq(cny.currency,'CNY','explicit currency preserved');
near(cny.amount,30,'separate month/currency group preserved');

subject.openingProviders=[{id:'p1',name:'Provider One',contacts:[{id:'contact-a',name:'Alice'}]}];
eq(subject.financeEntryProviderName({providerId:'p1'}),'Provider One','provider display lookup');
eq(subject.financeEntryProviderName({providerId:'missing'}),'未知开户商','provider fallback label');
eq(subject.financeEntryContactName({providerId:'p1',contactId:'contact-a'}),'Alice','contact display lookup');
eq(subject.financeEntryContactName({providerId:'p1',contactId:'missing'}),'未设置对接人','contact fallback label');
subject.financeChannelDeals=(providerId,contactId)=>[
  {clientId:'c1'},{clientId:'c1'},{clientId:'c2'},{clientId:''},
];
eq(subject.financeEntryLinkedClientCount({providerId:'p1',contactId:'contact-a'}),2,'linked client count deduplicates client ids and ignores blank');

console.log('BUSINESS_FINANCE_SETTLEMENT_OK: channel-month+expected-rebate+actual-share-fallback+void-filter+normalization+currency-profit=executed');
