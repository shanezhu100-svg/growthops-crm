import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_SOP_MUTATION_PROBE_FAILED: dist/app missing');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_SOP_MUTATION_PROBE_FAILED: no final app-inline JS artifacts');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

const defRe = /(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs = [...bundle.matchAll(defRe)];
const targets = [
  'ensureSopDailyTasks',
  'removeSopStep',
  'saveSopDailyTasks',
  'saveSopSettings',
  'saveSopTask',
];
for (const target of targets) {
  const index = defs.findIndex(match => match[1] === target);
  if (index < 0 || index + 1 >= defs.length) {
    throw new Error(`BUSINESS_SOP_MUTATION_PROBE_FAILED: method boundary missing: ${target}`);
  }
  const start = defs[index].index + defs[index][0].indexOf(target);
  const next = defs[index + 1].index + defs[index + 1][0].indexOf(defs[index + 1][1]);
  const source = bundle.slice(start, next).replace(/,\s*$/, '').trim();
  console.log(`SOP_PROBE ${target} ${JSON.stringify(source)}`);
}
throw new Error('BUSINESS_SOP_MUTATION_PROBE_STOP: temporary source capture complete');
