import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: dist/app missing');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

// Inventory the final shipped Vue method object rather than canonical/source snippets.
// A method is mutation-like when it crosses one of the durable/user-confirmed write
// boundaries already used by the CRM runtime. This deliberately excludes pure
// computed/display helpers so the review list stays focused on state-changing paths.
const defRe = /(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs = [...bundle.matchAll(defRe)];
if (defs.length < 20) throw new Error(`BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: method parser drifted; defs=${defs.length}`);
const reserved = new Set(['if','for','while','switch','catch','with','function','return']);

const candidates = new Map();
for (let i = 0; i + 1 < defs.length; i += 1) {
  const name = defs[i][1];
  if (reserved.has(name)) continue;
  const start = defs[i].index + defs[i][0].indexOf(name);
  const next = defs[i + 1].index + defs[i + 1][0].indexOf(defs[i + 1][1]);
  const source = bundle.slice(start, next);
  const signals = [];
  if (/\bthis\.persist\s*\(/.test(source)) signals.push('persist');
  if (/\bthis\.logAudit\s*\(/.test(source)) signals.push('audit');
  if (/\b(?:window\.)?confirm\s*\(/.test(source)) signals.push('confirm');
  if (/\bthis\.(?:clients|leads|financeReceivables|financeCosts|adData|ads|receivablePayments)\s*=/.test(source)) signals.push('state-replace');
  if (/\bthis\.(?:clients|leads|financeReceivables|financeCosts|adData|ads|receivablePayments)\.(?:push|splice)\s*\(/.test(source)) signals.push('state-mutate');
  if (signals.length) candidates.set(name, [...new Set(signals)].sort());
}

const names = [...candidates.keys()].sort();
if (!names.length) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: no mutation-like shipped methods found; detector drifted');

// Cross-reference the existing permanent business-regression corpus. A textual
// mention is not yet considered proof of behavioral coverage; this probe uses it
// only to shrink the manual review set. The permanent follow-up gate will classify
// each shipped mutation explicitly rather than treating a comment/string as coverage.
const businessFiles = fs.readdirSync(root)
  .filter(name => /^test_business_.*\.mjs$/.test(name) && name !== 'test_business_persisted_mutation_inventory.mjs')
  .sort();
const businessText = businessFiles.map(name => fs.readFileSync(path.join(root, name), 'utf8')).join('\n');
const unmentioned = names.filter(name => !new RegExp(`\\b${name}\\b`).test(businessText));
const rendered = names.map(name => `${name}[${candidates.get(name).join('+')}]`);

// Probe mode is intentionally non-mergeable. CI gives us the exact shipped
// inventory and the smaller unmentioned set; the follow-up commit replaces this
// sentinel with a reviewed classification and permanent drift gate.
const EXPECTED = null;
if (EXPECTED === null) {
  throw new Error(
    `BUSINESS_PERSISTED_MUTATION_INVENTORY_PROBE: methods=${names.length}; ` +
    `unmentioned=${unmentioned.length}:${unmentioned.join(',') || '-'}; inventory=` + rendered.join(',')
  );
}

console.log(`BUSINESS_PERSISTED_MUTATION_INVENTORY_OK: methods=${names.length}`);
