import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: dist/app missing');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

// Provenance proof: compile an actual shipped method in a VM before using source
// inspection for the inventory. This keeps the gate under the same read+execute
// requirement as every permanent business regression without invoking side effects.
const proofMarker = 'adRecordMetrics(record){';
const proofNext = 'adDataDraftMetrics(){';
const proofStart = bundle.indexOf(proofMarker);
const proofEnd = proofStart < 0 ? -1 : bundle.indexOf(proofNext, proofStart + proofMarker.length);
if (proofStart < 0 || proofEnd < 0) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: shipped provenance proof markers drifted');
const proofSource = bundle.slice(proofStart, proofEnd).replace(/,\s*$/, '').trim();
const proof = vm.runInNewContext(`({${proofSource}})`, Object.create(null), { timeout: 1000 });
if (typeof proof.adRecordMetrics !== 'function') throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: shipped provenance method not executable');

// Inventory the final shipped Vue method object rather than canonical/source snippets.
// Internal _legacy* methods are implementation details of reviewed public wrappers:
// when a wrapper delegates to one, inherit that legacy method's direct write signals
// onto the public method instead of inventing a second mutation surface.
//
// Keep the broad historical regex discovery pass so unknown new public methods remain
// visible. When its *next* hit is a reserved control-flow keyword, that hit is nested
// implementation rather than a method boundary; only then repair the current method's
// end with a brace-aware scanner. This fixes multiline deleteAlert without deep-scanning
// every regex false-positive in the bundle.
const defRe = /(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs = [...bundle.matchAll(defRe)];
if (defs.length < 20) throw new Error(`BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: method parser drifted; defs=${defs.length}`);
const reserved = new Set(['if','for','while','switch','catch','with','function','return']);

function methodEnd(text, open, name) {
  let depth = 0, quote = '', escaped = false, lineComment = false, blockComment = false;
  for (let i = open; i < text.length; i += 1) {
    const ch = text[i], next = text[i + 1] || '';
    if (lineComment) { if (ch === '\n') lineComment = false; continue; }
    if (blockComment) { if (ch === '*' && next === '/') { blockComment = false; i += 1; } continue; }
    if (quote) {
      if (escaped) { escaped = false; continue; }
      if (ch === '\\') { escaped = true; continue; }
      if (ch === quote) quote = '';
      continue;
    }
    if (ch === '/' && next === '/') { lineComment = true; i += 1; continue; }
    if (ch === '/' && next === '*') { blockComment = true; i += 1; continue; }
    if (ch === '"' || ch === "'" || ch === '`') { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return i + 1;
  }
  throw new Error(`BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: ${name} repaired boundary missing closing brace`);
}

const sources = new Map();
let repairedReservedBoundaries = 0;
for (let i = 0; i + 1 < defs.length; i += 1) {
  const name = defs[i][1];
  const start = defs[i].index + defs[i][0].indexOf(name);
  const nextName = defs[i + 1][1];
  let end = defs[i + 1].index + defs[i + 1][0].indexOf(nextName);
  if (!reserved.has(name) && reserved.has(nextName)) {
    const open = bundle.indexOf('{', start);
    if (open < 0) throw new Error(`BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: ${name} opening brace missing`);
    end = methodEnd(bundle, open, name);
    repairedReservedBoundaries += 1;
  }
  sources.set(name, bundle.slice(start, end));
}
if (!repairedReservedBoundaries) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: expected at least one reserved-boundary repair');
const deleteAlertSource = sources.get('deleteAlert') || '';
if (!deleteAlertSource.includes('this.persist()') || !deleteAlertSource.includes("this.logAudit('删除独立提醒'")) {
  throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: deleteAlert multiline mutation boundary is still truncated');
}

function directSignals(source) {
  const signals = [];
  if (/\bthis\.persist\s*\(/.test(source)) signals.push('persist');
  if (/\bthis\.logAudit\s*\(/.test(source)) signals.push('audit');
  if (/\b(?:window\.)?confirm\s*\(/.test(source)) signals.push('confirm');
  if (/\bthis\.(?:clients|leads|openingDeals|openingProviders|financeReceivables|financeCosts|adData|ads|receivablePayments)\s*=/.test(source)) signals.push('state-replace');
  if (/\bthis\.(?:clients|leads|openingDeals|openingProviders|financeReceivables|financeCosts|adData|ads|receivablePayments)\.(?:push|unshift|splice)\s*\(/.test(source)) signals.push('state-mutate');
  return signals;
}

const candidates = new Map();
for (const [name, source] of sources) {
  if (reserved.has(name) || name.startsWith('_legacy')) continue;
  const signals = directSignals(source);
  const delegatedLegacyNames = [...new Set([...source.matchAll(/(_legacy[A-Za-z_$][A-Za-z0-9_$]*)/g)].map(match => match[1]))];
  for (const legacyName of delegatedLegacyNames) {
    const legacySource = sources.get(legacyName);
    if (!legacySource) continue;
    signals.push(...directSignals(legacySource));
  }
  if (signals.length) candidates.set(name, [...new Set(signals)].sort());
}

const names = [...candidates.keys()].sort();
if (!names.length) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: no mutation-like shipped methods found; detector drifted');
const rendered = names.map(name => `${name}[${candidates.get(name).join('+')}]`);

// Reviewed shipped mutation surface. Pin both method identity and durable-boundary
// signals: a newly introduced write path, a removed method, or a method that stops
// crossing its reviewed persist/audit/state boundary must be explicitly reviewed.
const EXPECTED = [
  'addAdCampaign[persist]',
  'addAdSet[persist]',
  'addCreative[persist]',
  'applyBackupPayload[persist+state-replace]',
  'archiveClient[audit+persist]',
  'createBackupSnapshot[audit]',
  'createReceivableForClientMonth[state-mutate]',
  'deleteAdDataRecord[audit+persist]',
  'deleteAlert[audit+persist]',
  'deleteAuthUser[audit+persist]',
  'deleteBackupSnapshot[audit]',
  'deleteClient[audit+persist+state-replace]',
  'deleteExternalAsset[audit+persist]',
  'deleteFinanceCost[audit+persist+state-replace]',
  'deleteLead[audit+persist+state-replace]',
  'deleteMediaTool[audit+persist]',
  'deleteReceivable[audit+persist+state-replace]',
  'deleteReceivablePayment[audit+persist]',
  'deleteReminderType[audit+persist]',
  'downloadFullBackup[audit]',
  'editAdCampaign[persist]',
  'ensureAutomaticAssetCosts[persist+state-mutate+state-replace]',
  'ensureAutomaticReceivables[audit+persist]',
  'ensureSopDailyTasks[persist]',
  'exportFinanceExcel[audit]',
  'exportRebateExcel[audit]',
  'generateReceivablesForPeriod[audit+persist]',
  'importFullBackup[audit]',
  'loadData[state-replace]',
  'login[audit]',
  'logout[audit]',
  'migrateLegacyAccountSpendRecords[audit]',
  'migrateOpeningDeals[state-replace]',
  'navigateTo[persist]',
  'openConvertedLeadClient[persist]',
  'removeAdCampaign[audit+persist]',
  'removeAdSet[audit+persist]',
  'removeCreative[audit+persist]',
  'removeSopStep[audit]',
  'restoreBackupSnapshot[audit]',
  'restoreClient[audit+persist]',
  'restoreDismissedAlerts[audit+persist]',
  'runFinanceMonthCheck[persist]',
  'saveAdDataRecord[audit+persist]',
  'saveAdSpend[persist]',
  'saveAdsPlan[audit+persist]',
  'saveAuthUser[audit+persist]',
  'saveClient[audit+persist+state-mutate]',
  'saveExternalAsset[audit+persist]',
  'saveFinanceCost[audit+persist+state-mutate]',
  'saveLead[audit+persist+state-mutate]',
  'saveMediaTool[audit+persist]',
  'saveOpeningDeal[audit+persist+state-mutate]',
  'saveOpeningProvider[audit+persist+state-mutate]',
  'saveReceivable[audit+persist+state-mutate]',
  'saveReceivablePayment[audit+persist]',
  'saveRecharge[audit+persist]',
  'saveRechargeReminder[persist]',
  'saveReconciliation[audit+persist]',
  'saveReminderType[audit+persist]',
  'saveRenewal[audit+persist]',
  'saveSopDailyTasks[persist]',
  'saveSopSettings[audit+persist]',
  'saveSopTask[audit+persist]',
  'saveStandaloneAlert[audit+persist]',
  'syncFinancePeriodAutoCosts[persist]',
  'syncOpeningFeeCost[state-mutate+state-replace]',
  'syncReceivableLinkedCost[state-mutate+state-replace]',
  'toggleFinanceMonthLock[audit+persist]',
  'voidReconciliation[audit+persist]',
];

if (JSON.stringify(rendered) !== JSON.stringify(EXPECTED)) {
  const expectedSet = new Set(EXPECTED);
  const actualSet = new Set(rendered);
  const added = rendered.filter(item => !expectedSet.has(item));
  const removed = EXPECTED.filter(item => !actualSet.has(item));
  throw new Error(
    `BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: shipped mutation surface drifted; ` +
    `added=${added.join(',') || '-'}; removed-or-signal-changed=${removed.join(',') || '-'}`
  );
}

// Informational coverage-debt metric only. Textual mention is intentionally not
// treated as behavioral proof; permanent behavior tests still must execute shipped
// methods under the reachability/provenance gate.
const businessFiles = fs.readdirSync(root)
  .filter(name => /^test_business_.*\.mjs$/.test(name) && name !== 'test_business_persisted_mutation_inventory.mjs')
  .sort();
const businessText = businessFiles.map(name => fs.readFileSync(path.join(root, name), 'utf8')).join('\n');
const unmentioned = names.filter(name => !new RegExp(`\\b${name}\\b`).test(businessText));

console.log(
  `BUSINESS_PERSISTED_MUTATION_INVENTORY_OK: methods=${names.length}; repaired-reserved-boundaries=${repairedReservedBoundaries}; ` +
  `surface=public-name+selective-brace-aware-direct/delegated-signals-pinned; provenance=read+vm-execute; unmentioned-business-test-debt=${unmentioned.length}`
);