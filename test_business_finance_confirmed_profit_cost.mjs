import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: final runtime ${name} implementation not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: ${name} boundary parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['financeActualNetProfitGroups','financeExpectedNetProfitGroups','financeProfitBreakdownRows'];
const methods={};
for(const name of names){
  const obj=vm.runInNewContext(`({${extractMethod(name)}})`,{Number,String,Object,Array,Math,Set,Map},{timeout:1000});
  methods[name]=obj[name];
  if(typeof methods[name]!=='function')throw new Error(`BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: ${name} did not compile to a function`);
}
const call=(name,subject,...args)=>methods[name].call(subject,...args);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const mergeSpendGroups=(target,source)=>{for(const [currency,value] of Object.entries(source||{}))target[currency]=(target[currency]||0)+Number(value||0);return target;};
const subtractSpendGroups=(left,right)=>{const out={};for(const currency of new Set([...Object.keys(left||{}),...Object.keys(right||{})]))out[currency]=Number(left?.[currency]||0)-Number(right?.[currency]||0);return out;};

// Regression for the reported case: CNY 12,000 income and CNY 2,520 customer-owned
// cost. The ALL-scope confirmed profit must not deduct that customer cost a second
// time. Expected profit remains unchanged by this narrow fix.
let subject={
  financeActiveSnapshotScope:null,
  financeClientFilter:'ALL',
  financeReceivableTotals:{expected:{CNY:12000}},
  financeConfirmedActualRebateGroups:{},
  financeTotals:{expected:{}},
  financeCostGroups:{CNY:2520},
  financeCompanyNonClientCostGroups:{},
  mergeSpendGroups,subtractSpendGroups,
};
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:12000},'ALL confirmed profit excludes already client-attributed cost');
jsonEq(call('financeExpectedNetProfitGroups',subject),{CNY:9480},'expected profit remains income minus all visible costs');

// A selected client's own profitability must still deduct that client's costs.
subject.financeClientFilter='client-1';
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:9480},'selected-client confirmed profit still deducts client cost');

// Company project/public costs remain real aggregate costs and must still reduce
// ALL-scope confirmed profit.
subject.financeClientFilter='ALL';
subject.financeCompanyNonClientCostGroups={CNY:500};
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:11500},'ALL confirmed profit still deducts company non-client cost');

// The formula/breakdown shown next to confirmed profit must use the same cost basis
// as the number itself. EXPECTED remains total-cost based; ACTUAL switches only for
// ALL scope and returns to client-cost basis for a selected client.
subject={
  financeClientFilter:'ALL',
  financeReceivableTotals:{expected:{CNY:12000}},
  financeTotals:{expected:{}},
  financeConfirmedActualRebateGroups:{},
  financeCostGroups:{CNY:2520},
  financeCompanyNonClientCostGroups:{},
  financeExpectedNetProfitGroups:{CNY:9480},
  financeActualNetProfitGroups:{CNY:12000},
  formatMoney(value,currency){return `${currency}:${Number(value||0).toFixed(2)}`;},
};
let rows=call('financeProfitBreakdownRows',subject,'EXPECTED');
let cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,2520,'expected breakdown keeps total cost');
eq(cny.net,9480,'expected breakdown net remains unchanged');
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,0,'ALL confirmed breakdown excludes customer-owned cost');
eq(cny.net,12000,'ALL confirmed breakdown matches corrected net');
eq(cny.costText,'CNY:0.00','ALL confirmed formula renders corrected cost basis');

subject.financeClientFilter='client-1';
subject.financeActualNetProfitGroups={CNY:9480};
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,2520,'selected-client confirmed breakdown still shows client cost');
eq(cny.net,9480,'selected-client confirmed breakdown keeps client profitability');

// Currency inventory regression: a company/public cost can exist in a currency with
// no receivable/income. ALL confirmed profit must still carry that currency through
// the aggregate and the breakdown as a negative net instead of silently dropping it.
subject={
  financeActiveSnapshotScope:null,
  financeClientFilter:'ALL',
  financeReceivableTotals:{expected:{CNY:12000}},
  financeConfirmedActualRebateGroups:{},
  financeTotals:{expected:{}},
  financeCostGroups:{CNY:2520,USD:200},
  financeCompanyNonClientCostGroups:{USD:200},
  mergeSpendGroups,subtractSpendGroups,
  formatMoney(value,currency){return `${currency}:${Number(value||0).toFixed(2)}`;},
};
const crossCurrencyActual=call('financeActualNetProfitGroups',subject);
eq(crossCurrencyActual.CNY,12000,'cross-currency ALL confirmed keeps CNY income without client-cost double deduction');
eq(crossCurrencyActual.USD,-200,'company-only USD cost survives as negative confirmed profit');
subject.financeExpectedNetProfitGroups={CNY:9480,USD:-200};
subject.financeActualNetProfitGroups=crossCurrencyActual;
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
const usd=rows.find(row=>row.currency==='USD');
if(!usd)throw new Error('BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: company-only USD cost currency missing from ACTUAL breakdown');
eq(usd.cost,200,'company-only USD cost remains visible in ACTUAL breakdown');
eq(usd.net,-200,'company-only USD cost produces negative USD confirmed profit');
eq(usd.costText,'USD:200.00','company-only USD formula formats the retained cost basis');

// Future company/all-client month snapshots must use the same corrected cost basis.
// Existing locked snapshots remain immutable because financeActualNetProfitGroups
// still returns a stored snapshot value before entering live arithmetic.
const snapshotSource=extractMethod('buildFinanceMonthSnapshot');
const clientAnchor='actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),costGroups)';
const companyAnchor='actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))';
eq(snapshotSource.split(clientAnchor).length-1,1,'future snapshot preserves one client-level actual-profit cost deduction');
eq(snapshotSource.split(companyAnchor).length-1,1,'future company snapshot excludes direct client costs from aggregate confirmed profit');

console.log('BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_OK: all-confirmed=company-cost-only; customer-cost=no-double-deduct; selected-client=unchanged; expected=unchanged; breakdown=aligned; cross-currency-company-cost=retained; future-snapshot=aligned');
