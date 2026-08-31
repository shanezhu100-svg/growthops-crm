import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_AD_METRICS_FAILED: dist/app missing; run canonical build first');

const files = fs.readdirSync(appDir)
  .filter(name => /^app-inline-\d+\.js$/.test(name))
  .sort();
if (!files.length) throw new Error('BUSINESS_AD_METRICS_FAILED: no final app-inline JS artifacts found');

const marker = 'adRecordMetrics(record){';
const nextMarker = 'adDataDraftMetrics(){';
let methodSource = '';
let sourceFile = '';
for (const name of files) {
  const text = fs.readFileSync(path.join(appDir, name), 'utf8');
  const start = text.indexOf(marker);
  if (start < 0) continue;
  const next = text.indexOf(nextMarker, start + marker.length);
  if (next < 0) throw new Error(`BUSINESS_AD_METRICS_FAILED: ${name} contains adRecordMetrics without adjacent adDataDraftMetrics boundary`);
  methodSource = text.slice(start, next).replace(/,\s*$/, '').trim();
  sourceFile = name;
  break;
}
if (!methodSource) throw new Error('BUSINESS_AD_METRICS_FAILED: final runtime adRecordMetrics implementation not found');

const factorySource = `({
  formatMoney(value, currency){ return String(currency) + ':' + Number(value).toFixed(4); },
  ${methodSource}
})`;
let subject;
try {
  subject = vm.runInNewContext(factorySource, Object.create(null), { timeout: 1000 });
} catch (error) {
  throw new Error(`BUSINESS_AD_METRICS_FAILED: unable to execute final adRecordMetrics implementation: ${error.message}`);
}
if (typeof subject.adRecordMetrics !== 'function') throw new Error('BUSINESS_AD_METRICS_FAILED: extracted method is not executable');

const assertEq = (actual, expected, label) => {
  if (actual !== expected) throw new Error(`BUSINESS_AD_METRICS_FAILED: ${label}; expected=${expected}; actual=${actual}`);
};

const normal = subject.adRecordMetrics({
  currency: 'USD',
  spend: 100,
  impressions: 10000,
  reach: 5000,
  clicks: 200,
  conversions: 20,
  revenue: 500,
});
assertEq(normal.cpmText, 'USD:10.0000', 'CPM must be spend / impressions * 1000');
assertEq(normal.reachText, '5,000', 'reach display must preserve count');
assertEq(normal.frequencyText, '2.00', 'frequency must be impressions / reach');
assertEq(normal.ctrText, '2.00%', 'CTR must be clicks / impressions');
assertEq(normal.cpcText, 'USD:0.5000', 'CPC must be spend / clicks');
assertEq(normal.cvrText, '10.00%', 'CVR must be conversions / clicks');
assertEq(normal.cpaText, 'USD:5.0000', 'CPA must be spend / conversions');
assertEq(normal.roasText, '5.00', 'ROAS must be revenue / spend');

const zero = subject.adRecordMetrics({ currency: 'USD', spend: 0, impressions: 0, reach: 0, clicks: 0, conversions: 0, revenue: 0 });
for (const key of ['cpmText','reachText','frequencyText','ctrText','cpcText','cvrText','cpaText','roasText']) {
  assertEq(zero[key], '—', `${key} must fail closed to em dash when its denominator/count is zero`);
}

const sparse = subject.adRecordMetrics({ currency: 'CNY', spend: 80, impressions: 0, reach: 40, clicks: 0, conversions: 0, revenue: 160 });
assertEq(sparse.cpmText, '—', 'CPM must not divide by zero impressions');
assertEq(sparse.frequencyText, '0.00', 'frequency may be zero when reach exists but impressions are zero');
assertEq(sparse.cpcText, '—', 'CPC must not divide by zero clicks');
assertEq(sparse.cvrText, '—', 'CVR must not divide by zero clicks');
assertEq(sparse.cpaText, '—', 'CPA must not divide by zero conversions');
assertEq(sparse.roasText, '2.00', 'ROAS remains valid when spend is positive');

console.log(`BUSINESS_AD_METRICS_OK: source=${sourceFile}; cpm+frequency+ctr+cpc+cvr+cpa+roas=executed; zero-denominators=guarded`);
await import('./test_business_ad_summary.mjs');
await import('./test_business_finance_reconciliation_cost.mjs');
await import('./test_business_finance_confirmed_profit_cost.mjs');
await import('./test_business_client_module_home.mjs');
