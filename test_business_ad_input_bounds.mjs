import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir = path.join(process.cwd(), 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_AD_INPUT_BOUNDS_FAILED: dist/app missing; run canonical build first');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_AD_INPUT_BOUNDS_FAILED: no final app-inline JS artifacts found');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

const startMarker = 'saveAdDataRecord(){';
const start = bundle.indexOf(startMarker);
if (start < 0) throw new Error('BUSINESS_AD_INPUT_BOUNDS_FAILED: saveAdDataRecord implementation not found');
const methodRe = /(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
methodRe.lastIndex = start + startMarker.length;
const next = methodRe.exec(bundle);
if (!next) throw new Error('BUSINESS_AD_INPUT_BOUNDS_FAILED: saveAdDataRecord boundary not found');
const end = next.index + next[0].indexOf(next[1]);
const methodSource = bundle.slice(start, end).replace(/,\s*$/, '').trim();

let subjectFactory;
try {
  subjectFactory = vm.runInNewContext(`(function(){return {${methodSource}}})`, Object.create(null), { timeout: 1000 });
} catch (error) {
  throw new Error(`BUSINESS_AD_INPUT_BOUNDS_FAILED: unable to compile final saveAdDataRecord: ${error.message}`);
}

const fields = ['spend', 'impressions', 'reach', 'clicks', 'leads', 'conversions', 'revenue'];
const invalidValues = [-1, 'abc', 'Infinity'];

function makeSubject({ overrides = {}, existing = false } = {}) {
  const counters = { persist: 0, accountSync: 0, clientSync: 0, audit: 0, notify: [] };
  const existingRecord = {
    id: 'record-existing', date: '2026-08-31', campaignId: 'campaign-1', campaignName: 'Campaign',
    adSetId: 'adset-1', adSetName: 'Set', adId: 'ad-1', adName: 'Ad', currency: 'USD',
    spend: 10, impressions: 100, reach: 80, clicks: 5, leads: 2, conversions: 1, revenue: 20,
    createdAt: '2026-08-30T00:00:00.000Z', updatedAt: '2026-08-30T00:00:00.000Z',
  };
  const account = {
    accountName: 'Account', adAccountId: 'acct-1', adSpendCurrency: 'USD',
    adDataRecords: existing ? [{ ...existingRecord }] : [],
  };
  const client = { name: 'Client' };
  const campaign = {
    id: 'campaign-1', name: 'Campaign', planName: 'Plan',
    adSets: [{ id: 'adset-1', name: 'Set', ads: [{ id: 'ad-1', name: 'Ad' }] }],
  };
  const form = {
    date: '2026-08-31', campaignId: 'campaign-1', adSetId: 'adset-1', adId: 'ad-1', currency: 'USD',
    spend: 10, impressions: 100, reach: 80, clicks: 5, leads: 2, conversions: 1, revenue: 20,
    video3sRate: '', video25Rate: '', video50Rate: '', video75Rate: '', video95Rate: '', videoCompleteRate: '',
    note: '', ...overrides,
  };
  const subject = Object.assign(subjectFactory(), {
    selectedAdsClient: client,
    selectedAdsAccount: account,
    selectedAdsPlatform: 'FB',
    savedAdsCampaignsForAccount: [campaign],
    adDataForm: form,
    editingAdDataRecordId: existing ? existingRecord.id : null,
    showAdDataModal: true,
    assertMonthUnlocked(){ return true; },
    localDateKey(){ return '2026-08-31'; },
    normalizePercent(value){ if (value === '' || value === null || value === undefined) return null; const n = Number(value); return Number.isFinite(n) ? n : null; },
    adDataIdentity(record){ return `${record.date}|${record.campaignId}|${record.adSetId}|${record.adId}`; },
    accountUid(){ return 'record-new'; },
    syncAccountAnalyticsFromRecords(){ counters.accountSync++; },
    syncClientPlatformAnalytics(){ counters.clientSync++; },
    persist(){ counters.persist++; },
    logAudit(){ counters.audit++; },
    notify(message){ counters.notify.push(String(message)); },
    formatMoney(value, currency){ return `${currency}:${Number(value).toFixed(2)}`; },
  });
  return { subject, account, counters, existingRecord };
}

function assert(condition, message) {
  if (!condition) throw new Error('BUSINESS_AD_INPUT_BOUNDS_FAILED: ' + message);
}

for (const field of fields) {
  for (const invalid of invalidValues) {
    const { subject, account, counters } = makeSubject({ overrides: { [field]: invalid } });
    subject.saveAdDataRecord();
    assert(account.adDataRecords.length === 0, `${field}=${String(invalid)} created a record`);
    assert(counters.persist === 0, `${field}=${String(invalid)} reached persist`);
    assert(counters.accountSync === 0 && counters.clientSync === 0, `${field}=${String(invalid)} reached analytics sync`);
    assert(counters.audit === 0, `${field}=${String(invalid)} reached audit`);
    assert(counters.notify.length >= 1, `${field}=${String(invalid)} did not produce validation feedback`);
  }
}

for (const field of fields) {
  const { subject, account, counters, existingRecord } = makeSubject({ overrides: { [field]: -1 }, existing: true });
  subject.saveAdDataRecord();
  assert(account.adDataRecords.length === 1, `${field} invalid edit changed record count`);
  assert(JSON.stringify(account.adDataRecords[0]) === JSON.stringify(existingRecord), `${field} invalid edit mutated existing record`);
  assert(counters.persist === 0 && counters.audit === 0, `${field} invalid edit reached persist/audit`);
}

const zeroOverrides = Object.fromEntries(fields.map(field => [field, 0]));
const zeroCase = makeSubject({ overrides: zeroOverrides });
zeroCase.subject.saveAdDataRecord();
assert(zeroCase.account.adDataRecords.length === 1, 'all-zero valid record was not saved');
for (const field of fields) assert(zeroCase.account.adDataRecords[0][field] === 0, `zero ${field} was not preserved`);
assert(zeroCase.counters.persist === 1, 'all-zero valid record did not persist exactly once');
assert(zeroCase.counters.accountSync === 1 && zeroCase.counters.clientSync === 1, 'all-zero valid record did not sync analytics exactly once');
assert(zeroCase.counters.audit === 1, 'all-zero valid record did not audit exactly once');

console.log('BUSINESS_AD_INPUT_BOUNDS_OK: spend+impressions+reach+clicks+leads+conversions+revenue=finite-nonnegative; negative+nan+infinity=denied-before-mutation/sync/persist/audit; edit=unchanged-on-invalid; zero=preserved');
