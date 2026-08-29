import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_AD_SUMMARY_FAILED: dist/app missing; run canonical build first');

const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_AD_SUMMARY_FAILED: no final app-inline JS artifacts found');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

function extract(startMarker, endMarker, label) {
  const start = bundle.indexOf(startMarker);
  if (start < 0) throw new Error(`BUSINESS_AD_SUMMARY_FAILED: final runtime ${label} implementation not found`);
  const end = bundle.indexOf(endMarker, start + startMarker.length);
  if (end < 0) throw new Error(`BUSINESS_AD_SUMMARY_FAILED: ${label} boundary marker not found`);
  return bundle.slice(start, end).replace(/,\s*$/, '').trim();
}

const spendGroupsSource = extract("accountDataSpendGroups(account,dateFilter='ALL'){", 'accountSpendText(account){', 'accountDataSpendGroups');
const summarySource = extract("accountDataSummary(account,dateFilter='ALL'){", 'syncAccountAnalyticsFromRecords(account){', 'accountDataSummary');

const factorySource = `({
  formatMoney(value, currency){ return String(currency) + ':' + Number(value).toFixed(2); },
  spendGroupsText(groups){ return Object.entries(groups).filter(([,v]) => Math.abs(Number(v||0)) >= 0.005).sort(([a],[b]) => a.localeCompare(b)).map(([k,v]) => k + ':' + Number(v).toFixed(2)).join('|') || '—'; },
  optionalNumber(value){ if(value === null || value === undefined || value === '') return null; const n=Number(value); return Number.isFinite(n) ? n : null; },
  ${spendGroupsSource},
  ${summarySource}
})`;

let subject;
try {
  subject = vm.runInNewContext(factorySource, Object.create(null), { timeout: 1000 });
} catch (error) {
  throw new Error(`BUSINESS_AD_SUMMARY_FAILED: unable to execute final summary implementation: ${error.message}`);
}

const assertEq = (actual, expected, label) => {
  if (actual !== expected) throw new Error(`BUSINESS_AD_SUMMARY_FAILED: ${label}; expected=${expected}; actual=${actual}`);
};

const account = {
  adSpendCurrency: 'USD',
  adDataRecords: [
    { date:'2026-08-01', currency:'USD', spend:100, impressions:1000, reach:800, clicks:100, leads:20, conversions:10, revenue:300, video3sRate:20, video25Rate:10, video50Rate:6, video75Rate:4, video95Rate:2, videoCompleteRate:1 },
    { date:'2026-08-02', currency:'USD', spend:50, impressions:500, reach:400, clicks:25, leads:5, conversions:5, revenue:100, video3sRate:40, video25Rate:20, video50Rate:12, video75Rate:8, video95Rate:4, videoCompleteRate:2 },
  ],
};
const normal = subject.accountDataSummary(account);
assertEq(normal.records, 2, 'record count');
assertEq(normal.spendText, 'USD:150.00', 'same-currency spend sum');
assertEq(normal.impressions, 1500, 'impression sum');
assertEq(normal.reach, 1200, 'reach sum');
assertEq(normal.clicks, 125, 'click sum');
assertEq(normal.leads, 25, 'lead sum');
assertEq(normal.conversions, 15, 'conversion sum');
assertEq(normal.revenueText, 'USD:400.00', 'revenue sum');
assertEq(normal.cplText, 'USD:6.00', 'CPL');
assertEq(normal.cpmText, 'USD:100.00', 'CPM');
assertEq(normal.frequencyText, '1.25', 'frequency');
assertEq(normal.ctrText, '8.33%', 'CTR');
assertEq(normal.cpcText, 'USD:1.20', 'CPC');
assertEq(normal.cvrText, '12.00%', 'CVR');
assertEq(normal.cpaText, 'USD:10.00', 'CPA');
assertEq(normal.roasText, '2.67', 'ROAS');
assertEq(normal.video3sRateText, '26.67%', 'video 3s impression-weighted rate');
assertEq(normal.video25RateText, '13.33%', 'video 25 impression-weighted rate');
assertEq(normal.video50RateText, '8.00%', 'video 50 impression-weighted rate');
assertEq(normal.video75RateText, '5.33%', 'video 75 impression-weighted rate');
assertEq(normal.video95RateText, '2.67%', 'video 95 impression-weighted rate');
assertEq(normal.videoCompleteRateText, '1.33%', 'video complete impression-weighted rate');

const dayOne = subject.accountDataSummary(account, '2026-08-01');
assertEq(dayOne.records, 1, 'date filter record count');
assertEq(dayOne.spendText, 'USD:100.00', 'date filter spend');
assertEq(dayOne.roasText, '3.00', 'date filter ROAS');
assertEq(dayOne.video3sRateText, '20.00%', 'date filter weighted metric');

const mixed = subject.accountDataSummary({
  adDataRecords: [
    { date:'2026-08-03', currency:'USD', spend:100, impressions:1000, reach:800, clicks:100, leads:10, conversions:10, revenue:250, video3sRate:20 },
    { date:'2026-08-03', currency:'CNY', spend:700, impressions:1000, reach:700, clicks:50, leads:5, conversions:5, revenue:1400, video3sRate:40 },
  ],
});
assertEq(mixed.spendText, 'CNY:700.00|USD:100.00', 'mixed currencies stay separated');
assertEq(mixed.cplText, '—', 'mixed-currency CPL must not be combined');
assertEq(mixed.cpmText, '—', 'mixed-currency CPM must not be combined');
assertEq(mixed.cpcText, '—', 'mixed-currency CPC must not be combined');
assertEq(mixed.cpaText, '—', 'mixed-currency CPA must not be combined');
assertEq(mixed.roasText, '—', 'mixed-currency ROAS must not be combined');
assertEq(mixed.frequencyText, '1.33', 'count-based frequency remains valid across currencies');
assertEq(mixed.ctrText, '7.50%', 'count-based CTR remains valid across currencies');
assertEq(mixed.cvrText, '10.00%', 'count-based CVR remains valid across currencies');
assertEq(mixed.video3sRateText, '30.00%', 'video rate remains impression-weighted across currencies');

const fallback = subject.accountDataSummary({
  adDataRecords: [
    { date:'2026-08-04', currency:'USD', spend:0, impressions:0, reach:0, clicks:0, leads:0, conversions:0, revenue:0, video3sRate:20, videoCompleteRate:10 },
    { date:'2026-08-04', currency:'USD', spend:0, impressions:0, reach:0, clicks:0, leads:0, conversions:0, revenue:0, video3sRate:40, videoCompleteRate:30 },
  ],
});
assertEq(fallback.video3sRateText, '30.00%', 'zero-impression video rate falls back to simple mean');
assertEq(fallback.videoCompleteRateText, '20.00%', 'zero-impression complete rate falls back to simple mean');
assertEq(fallback.frequencyText, '—', 'zero reach does not divide');
assertEq(fallback.ctrText, '—', 'zero impressions does not divide');

console.log('BUSINESS_AD_SUMMARY_OK: same-currency-math+date-filter+mixed-currency-deny+video-weighting+zero-impression-fallback=executed');
