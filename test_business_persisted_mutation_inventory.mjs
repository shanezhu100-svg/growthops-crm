import fs from 'node:fs';
import path from 'node:path';

const appDir = path.join(process.cwd(), 'dist', 'app');
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

const candidates = [];
for (let i = 0; i + 1 < defs.length; i += 1) {
  const name = defs[i][1];
  const start = defs[i].index + defs[i][0].indexOf(name);
  const next = defs[i + 1].index + defs[i + 1][0].indexOf(defs[i + 1][1]);
  const source = bundle.slice(start, next);
  const signals = [];
  if (/\bthis\.persist\s*\(/.test(source)) signals.push('persist');
  if (/\bthis\.logAudit\s*\(/.test(source)) signals.push('audit');
  if (/\b(?:window\.)?confirm\s*\(/.test(source)) signals.push('confirm');
  if (/\bthis\.(?:clients|leads|financeReceivables|financeCosts|adData|ads|receivablePayments)\s*=/.test(source)) signals.push('state-replace');
  if (/\bthis\.(?:clients|leads|financeReceivables|financeCosts|adData|ads|receivablePayments)\.(?:push|splice)\s*\(/.test(source)) signals.push('state-mutate');
  if (signals.length) candidates.push(`${name}[${[...new Set(signals)].join('+')}]`);
}

const unique = [...new Set(candidates)].sort();
if (!unique.length) throw new Error('BUSINESS_PERSISTED_MUTATION_INVENTORY_FAILED: no mutation-like shipped methods found; detector drifted');

// Probe mode is intentionally non-mergeable. The first CI run gives us the exact
// shipped inventory; the follow-up commit will replace this sentinel with a reviewed
// classification and permanent coverage gate.
const EXPECTED = null;
if (EXPECTED === null) {
  throw new Error(
    `BUSINESS_PERSISTED_MUTATION_INVENTORY_PROBE: methods=${unique.length}; ` + unique.join(',')
  );
}

console.log(`BUSINESS_PERSISTED_MUTATION_INVENTORY_OK: methods=${unique.length}`);
