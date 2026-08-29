import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_COST_VISIBILITY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_COST_VISIBILITY_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_COST_VISIBILITY_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_COST_VISIBILITY_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=[
  'financeVisibleCosts','financeCostAllocatedTotal','financeCostUnallocatedAmount',
  'financeCostCategoryText','financeCostScopeText','financeCostClientName',
  'financeCostText','financeVisibleCostAllocatedText','financeUnallocatedCompanyCostText',
  'financeUnallocatedCompanyCostNonZero'
];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
function makeSubject(){
  const factory=`({
    financeCosts:[], clients:[], financeClientFilter:'ALL', financeCostGroups:{USD:12.5,CNY:8}, financeUnallocatedCompanyCostGroups:{USD:3},
    financeDateMatch(date){return /^2026-(08|09)-/.test(String(date||''));},
    financeCostAllocatedAmountForClient(cost,client){if(!client)return 0;return Number(cost?.allocations?.[String(client.id)]||0);},
    formatMoney(value,currency){return String(currency)+':'+Number(value||0).toFixed(2);},
    spendGroupsText(groups){return Object.entries(groups||{}).map(([currency,value])=>currency+':'+String(value)).join('|');},
    ${names.map(name=>sources[name]).join(',\n    ')}
  })`;
  try{return vm.runInNewContext(factory,{Number,String,Object,Array,Math,RegExp},{timeout:1000});}
  catch(error){throw new Error(`BUSINESS_FINANCE_COST_VISIBILITY_FAILED: unable to execute final implementations: ${error.message}`);}
}
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_COST_VISIBILITY_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};

let subject=makeSubject();
subject.clients=[{id:'c1',name:'Client One'},{id:2,name:'Client Two'}];
subject.financeCosts=[
  {id:'c2-newest',date:'2026-09-11',scope:'CLIENT',clientId:2,amount:11,currency:'USD'},
  {id:'client-c1',date:'2026-09-10',scope:'CLIENT',clientId:'c1',amount:10,currency:'USD'},
  {id:'allocate-c1',date:'2026-09-09',scope:'ALLOCATE_SERVICE',amount:100,currency:'USD',allocations:{c1:25,2:75}},
  {id:'allocate-tiny',date:'2026-09-08',scope:'ALLOCATE_SPEND',amount:40,currency:'USD',allocations:{c1:0.0000001,2:39.9999999}},
  {id:'company-public',date:'2026-09-07',scope:'COMPANY',amount:20,currency:'CNY'},
  {id:'fallback-client',date:'2026-08-01',clientId:'c1',amount:5,currency:'USD'},
  {id:'out-period',date:'2026-10-01',scope:'CLIENT',clientId:'c1',amount:999,currency:'USD'},
];
jsonEq(subject.financeVisibleCosts().map(row=>row.id),['c2-newest','client-c1','allocate-c1','allocate-tiny','company-public','fallback-client'],'ALL client view uses date scope and descending date sort');
subject.financeClientFilter='c1';
jsonEq(subject.financeVisibleCosts().map(row=>row.id),['client-c1','allocate-c1','fallback-client'],'single-client view includes owned and materially allocated costs only');
subject.financeClientFilter='2';
jsonEq(subject.financeVisibleCosts().map(row=>row.id),['c2-newest','allocate-c1','allocate-tiny'],'string-normalized client matching and allocated costs');

subject=makeSubject();
subject.clients=[{id:'c1',name:'Client One'},{id:'c2',name:'Client Two'}];
eq(subject.financeCostAllocatedTotal(null),0,'null cost allocated total');
eq(subject.financeCostAllocatedTotal({scope:'CLIENT',amount:'12.5'}),12.5,'client cost allocated total equals direct amount');
const shared={scope:'ALLOCATE_SERVICE',amount:100,allocations:{c1:40,c2:15}};
eq(subject.financeCostAllocatedTotal(shared),55,'shared cost allocated total sums per-client allocations');
eq(subject.financeCostUnallocatedAmount(shared),45,'shared cost unallocated remainder');
eq(subject.financeCostUnallocatedAmount({scope:'ALLOCATE_SPEND',amount:50,allocations:{c1:60,c2:20}}),0,'oversubscribed allocation floors unallocated remainder at zero');
eq(subject.financeCostUnallocatedAmount({scope:'CLIENT',amount:99}),0,'client-owned cost has no unallocated remainder');
eq(subject.financeCostUnallocatedAmount({scope:'COMPANY_PROJECT',amount:99}),0,'company-project cost has no unallocated remainder');
eq(subject.financeCostUnallocatedAmount({scope:'COMPANY',amount:30}),30,'public company cost remains fully unallocated without client allocations');

subject=makeSubject();
eq(subject.financeCostCategoryText('IP'),'IP / 网络','IP cost category label');
eq(subject.financeCostCategoryText('CREATIVE'),'素材 / 设计','creative cost category label');
eq(subject.financeCostCategoryText('CUSTOM'),'CUSTOM','unknown cost category passes through');
eq(subject.financeCostScopeText({sourceType:'RECEIVABLE_ITEM',scope:'COMPANY_PROJECT'}),'收入项目联动 · 公司项目','receivable-linked company project scope');
eq(subject.financeCostScopeText({sourceType:'RECEIVABLE_ITEM',scope:'CLIENT'}),'收入项目联动 · 客户专属','receivable-linked client scope');
eq(subject.financeCostScopeText({scope:'CLIENT'}),'手动归属客户','manual client scope');
eq(subject.financeCostScopeText({scope:'COMPANY_PROJECT'}),'公司项目成本','company project scope');
eq(subject.financeCostScopeText({scope:'ALLOCATE_SERVICE'}),'按投放服务费比例分摊','service allocation scope');
eq(subject.financeCostScopeText({scope:'ALLOCATE_SPEND'}),'按广告消耗比例分摊','spend allocation scope');
eq(subject.financeCostScopeText({clientId:'c1'}),'手动归属客户','legacy clientId infers client scope');
eq(subject.financeCostScopeText({}),'公司公共成本 · 不分摊','default company-public scope');

subject=makeSubject();
subject.clients=[{id:1,name:'Numeric Client'}];
eq(subject.financeCostClientName({clientId:'1'}),'Numeric Client','client lookup normalizes id type');
eq(subject.financeCostClientName({clientId:'missing'}),'客户已归档 / 删除','missing client uses archived fallback');
eq(subject.financeCostClientName({}),'—','company cost has no client label');

subject=makeSubject();
eq(subject.financeCostText(),'USD:12.5|CNY:8','cost text delegates current grouped cost authority');
eq(subject.financeUnallocatedCompanyCostText(),'USD:3','unallocated company text delegates grouped authority');
subject.financeClientFilter='ALL';
eq(subject.financeVisibleCostAllocatedText({amount:100,currency:'USD'}),'USD:100.00','ALL view displays full cost amount');
subject.clients=[{id:'c1',name:'Client One'}];subject.financeClientFilter='c1';
eq(subject.financeVisibleCostAllocatedText({amount:100,currency:'USD',allocations:{c1:37.5}}),'USD:37.50','client view displays allocated share only');
subject.financeUnallocatedCompanyCostGroups={USD:0.005,CNY:-0.005};
eq(subject.financeUnallocatedCompanyCostNonZero(),false,'unallocated display ignores amounts at threshold');
subject.financeUnallocatedCompanyCostGroups={USD:0,CNY:-0.006};
eq(subject.financeUnallocatedCompanyCostNonZero(),true,'unallocated display detects material absolute amount');

console.log('BUSINESS_FINANCE_COST_VISIBILITY_OK: visible-filter+allocation+unallocated+scope-label+client-fallback+display=executed');
