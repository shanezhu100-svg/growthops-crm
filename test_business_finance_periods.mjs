import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_FINANCE_PERIODS_FAILED: dist/app missing; run canonical build first');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_FINANCE_PERIODS_FAILED: no final app-inline JS artifacts found');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

function extract(startMarker, endMarker, label) {
  const start = bundle.indexOf(startMarker);
  if (start < 0) throw new Error(`BUSINESS_FINANCE_PERIODS_FAILED: final runtime ${label} implementation not found`);
  const end = bundle.indexOf(endMarker, start + startMarker.length);
  if (end < 0) throw new Error(`BUSINESS_FINANCE_PERIODS_FAILED: ${label} boundary marker not found`);
  return bundle.slice(start, end).replace(/,\s*$/, '').trim();
}

const periodMonthsSource = extract('financePeriodMonths(){', 'financeSettlementMonthMatch(month){', 'financePeriodMonths');
const overlapSource = extract('clientContractOverlapsMonth(client,month){', 'financeClientActiveMonths(client){', 'clientContractOverlapsMonth');
const feeSource = extract('financeServiceFeeForClientMonth(client,month){', 'financeServiceFeeGroups(client,monthsOverride=null){', 'financeServiceFeeForClientMonth');
const feeGroupsSource = extract('financeServiceFeeGroups(client,monthsOverride=null){', 'financeDealsForClient(client){', 'financeServiceFeeGroups');

const factorySource = `({
  financePeriod:'MONTH', financeMonthKey:'2026-02', financeQuarter:1, financeQuarterYear:2026, financeYear:2026,
  financeReceivables:[],
  ${periodMonthsSource},
  ${overlapSource},
  ${feeSource},
  ${feeGroupsSource}
})`;
let subject;
try {
  subject = vm.runInNewContext(factorySource, { Date, Math, Number, Array, String, Set }, { timeout: 1000 });
} catch (error) {
  throw new Error(`BUSINESS_FINANCE_PERIODS_FAILED: unable to execute final finance implementations: ${error.message}`);
}
const assertEq = (actual, expected, label) => {
  if (actual !== expected) throw new Error(`BUSINESS_FINANCE_PERIODS_FAILED: ${label}; expected=${expected}; actual=${actual}`);
};
const assertJson = (actual, expected, label) => assertEq(JSON.stringify(actual), JSON.stringify(expected), label);

subject.financePeriod='MONTH'; subject.financeMonthKey='2026-02';
assertJson(subject.financePeriodMonths(), ['2026-02'], 'month period expansion');
subject.financePeriod='QUARTER'; subject.financeQuarterYear=2026; subject.financeQuarter=2;
assertJson(subject.financePeriodMonths(), ['2026-04','2026-05','2026-06'], 'quarter period expansion');
subject.financePeriod='YEAR'; subject.financeYear=2026;
const yearMonths=subject.financePeriodMonths();
assertEq(yearMonths.length, 12, 'year period month count');
assertEq(yearMonths[0], '2026-01', 'year period starts January');
assertEq(yearMonths[11], '2026-12', 'year period ends December');

const bounded={startDate:'2026-02-15',endDate:'2026-04-10'};
assertEq(subject.clientContractOverlapsMonth(bounded,'2026-01'), false, 'contract must not overlap month before start');
assertEq(subject.clientContractOverlapsMonth(bounded,'2026-02'), true, 'contract start month overlaps');
assertEq(subject.clientContractOverlapsMonth(bounded,'2026-04'), true, 'contract end month overlaps');
assertEq(subject.clientContractOverlapsMonth(bounded,'2026-05'), false, 'contract must not overlap month after end');

const full={id:'full',currency:'USD',billingMode:'FULL_MONTH',monthlyFee:300,startDate:'2026-02-15',endDate:'2026-04-10'};
assertEq(subject.financeServiceFeeForClientMonth(full,'2026-01'), 0, 'full-month fee outside contract');
assertEq(subject.financeServiceFeeForClientMonth(full,'2026-02'), 300, 'full-month fee charges full configured amount in active start month');
assertEq(subject.financeServiceFeeForClientMonth(full,'2026-04'), 300, 'full-month fee charges full configured amount in active end month');
assertEq(subject.financeServiceFeeForClientMonth(full,'2026-05'), 0, 'full-month fee after contract');

const prorate={id:'pro',currency:'USD',billingMode:'PRORATE',monthlyFee:280,startDate:'2026-02-15',endDate:'2026-02-20'};
assertEq(subject.financeServiceFeeForClientMonth(prorate,'2026-02'), 60, 'prorate includes both start and end dates: 6/28 of monthly fee');
const leap={id:'leap',currency:'USD',billingMode:'PRORATE',monthlyFee:290,startDate:'2028-02-15',endDate:''};
assertEq(subject.financeServiceFeeForClientMonth(leap,'2028-02'), 150, 'leap-February prorate uses 15/29 active days');
const cents={id:'cents',currency:'CNY',billingMode:'PRORATE',monthlyFee:100,startDate:'2026-04-02',endDate:'2026-04-02'};
assertEq(subject.financeServiceFeeForClientMonth(cents,'2026-04'), 3.33, 'prorate rounds to two decimals');

subject.financePeriod='QUARTER'; subject.financeQuarterYear=2026; subject.financeQuarter=1;
const groupedClient={id:'grp',currency:'USD',billingMode:'PRORATE',monthlyFee:310,startDate:'2026-01-16',endDate:'2026-03-15'};
const groups=subject.financeServiceFeeGroups(groupedClient);
assertEq(Object.keys(groups).length, 1, 'service fee groups preserve one contract currency');
assertEq(groups.USD, 160 + 310 + 150, 'quarter service-fee group sums monthly prorated/full values');

console.log('BUSINESS_FINANCE_PERIODS_OK: month+quarter+year+contract-overlap+full-month+prorate+leap-day+cent-rounding=executed');
await import('./test_business_finance_rebate_ownership.mjs');
