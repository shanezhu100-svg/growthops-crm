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

// Reviewed company/ALL rule: customer-specific/direct-client cost is not a company
// expected-profit cost basis. With CNY 12,000 income and CNY 2,520 customer-owned
// cost, BOTH expected and confirmed company net profit stay at CNY 12,000 when
// there is no company/non-client cost.
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
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:12000},'ALL confirmed profit excludes customer-specific cost');
jsonEq(call('financeExpectedNetProfitGroups',subject),{CNY:12000},'ALL expected profit excludes customer-specific cost');

// A selected client's own profitability keeps the existing client-cost basis.
subject.financeClientFilter='client-1';
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:9480},'selected-client confirmed profit still deducts client cost');
jsonEq(call('financeExpectedNetProfitGroups',subject),{CNY:9480},'selected-client expected profit still deducts client cost');

// Company/public costs are genuine ALL-scope costs. Full financeCostGroups contains
// both the CNY 2,520 customer cost and CNY 500 company cost; company authority is
// only CNY 500, so ALL expected/confirmed profit must be 11,500, not 8,980.
subject.financeClientFilter='ALL';
subject.financeCostGroups={CNY:3020};
subject.financeCompanyNonClientCostGroups={CNY:500};
jsonEq(call('financeActualNetProfitGroups',subject),{CNY:11500},'ALL confirmed profit deducts company non-client cost only');
jsonEq(call('financeExpectedNetProfitGroups',subject),{CNY:11500},'ALL expected profit deducts company non-client cost only');

// The displayed formula/breakdown must use exactly the same cost basis as the
// number. At ALL scope EXPECTED and ACTUAL both show only company/non-client cost.
subject={
  financeClientFilter:'ALL',
  financeReceivableTotals:{expected:{CNY:12000}},
  financeTotals:{expected:{}},
  financeConfirmedActualRebateGroups:{},
  financeCostGroups:{CNY:3020},
  financeCompanyNonClientCostGroups:{CNY:500},
  financeExpectedNetProfitGroups:{CNY:11500},
  financeActualNetProfitGroups:{CNY:11500},
  formatMoney(value,currency){return `${currency}:${Number(value||0).toFixed(2)}`;},
};
let rows=call('financeProfitBreakdownRows',subject,'EXPECTED');
let cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,500,'ALL expected breakdown uses company cost only');
eq(cny.net,11500,'ALL expected breakdown matches corrected net');
eq(cny.costText,'CNY:500.00','ALL expected formula renders company cost basis');
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,500,'ALL confirmed breakdown uses company cost only');
eq(cny.net,11500,'ALL confirmed breakdown matches corrected net');
eq(cny.costText,'CNY:500.00','ALL confirmed formula renders company cost basis');

// Selected-client breakdown keeps financeCostGroups unchanged.
subject.financeClientFilter='client-1';
subject.financeCostGroups={CNY:2520};
subject.financeExpectedNetProfitGroups={CNY:9480};
subject.financeActualNetProfitGroups={CNY:9480};
rows=call('financeProfitBreakdownRows',subject,'EXPECTED');
cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,2520,'selected-client expected breakdown still shows client cost');
eq(cny.net,9480,'selected-client expected breakdown keeps client profitability');
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
cny=rows.find(row=>row.currency==='CNY');
eq(cny.cost,2520,'selected-client confirmed breakdown still shows client cost');
eq(cny.net,9480,'selected-client confirmed breakdown keeps client profitability');

// Currency inventory regression: a company/public cost can exist in a currency with
// no receivable/income. It must survive in BOTH company expected and confirmed net,
// while the CNY customer-specific cost remains excluded from ALL profit.
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
const crossCurrencyExpected=call('financeExpectedNetProfitGroups',subject);
const crossCurrencyActual=call('financeActualNetProfitGroups',subject);
eq(crossCurrencyExpected.CNY,12000,'cross-currency ALL expected excludes client CNY cost');
eq(crossCurrencyExpected.USD,-200,'company-only USD cost survives in expected profit');
eq(crossCurrencyActual.CNY,12000,'cross-currency ALL confirmed excludes client CNY cost');
eq(crossCurrencyActual.USD,-200,'company-only USD cost survives in confirmed profit');
subject.financeExpectedNetProfitGroups=crossCurrencyExpected;
subject.financeActualNetProfitGroups=crossCurrencyActual;
for(const mode of ['EXPECTED','ACTUAL']){
  rows=call('financeProfitBreakdownRows',subject,mode);
  const usd=rows.find(row=>row.currency==='USD');
  if(!usd)throw new Error(`BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_FAILED: company-only USD cost currency missing from ${mode} breakdown`);
  eq(usd.cost,200,`${mode} company-only USD cost remains visible`);
  eq(usd.net,-200,`${mode} company-only USD cost produces negative USD profit`);
  eq(usd.costText,'USD:200.00',`${mode} company-only USD formula formats company cost basis`);
}

// Future company/all-client month snapshots must use the same reviewed basis for
// BOTH expected and actual profit. Existing locked snapshots stay immutable because
// live profit accessors still return stored snapshot values before live arithmetic.
const snapshotSource=extractMethod('buildFinanceMonthSnapshot');
const expectedClientAnchor='expectedNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,expectedRebateGroups),costGroups)';
const expectedCompanyAnchor='expectedNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,expectedRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))';
const actualClientAnchor='actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),costGroups)';
const actualCompanyAnchor='actualNetProfitGroups=this.subtractSpendGroups(this.financeProfitGroups(receivableGroups,actualRebateGroups),this.subtractSpendGroups(costGroups,directClientCostGroups))';
eq(snapshotSource.split(expectedClientAnchor).length-1,1,'future snapshot preserves one client expected-profit cost deduction');
eq(snapshotSource.split(expectedCompanyAnchor).length-1,1,'future company expected snapshot excludes direct client costs');
eq(snapshotSource.split(actualClientAnchor).length-1,1,'future snapshot preserves one client confirmed-profit cost deduction');
eq(snapshotSource.split(actualCompanyAnchor).length-1,1,'future company confirmed snapshot excludes direct client costs');

console.log('BUSINESS_FINANCE_CONFIRMED_PROFIT_COST_OK: all-profit=company-cost-only; customer-direct-cost=excluded-from-all-expected+confirmed; selected-client=unchanged; breakdown=aligned; cross-currency-company-cost=retained; future-snapshot=expected+actual-aligned');