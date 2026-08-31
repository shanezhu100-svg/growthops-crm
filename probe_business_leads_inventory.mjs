import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_LEADS_INVENTORY_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

// Inventory only final shipped method names. Do not print method bodies or runtime data.
const names=new Set();
for(const match of bundle.matchAll(/(?:^|[,\n])\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm)){
  const name=match[1];
  if(/lead|prospect|convert|client/i.test(name))names.add(name);
}
const sorted=[...names].sort((a,b)=>a.localeCompare(b));
console.log('BUSINESS_LEADS_INVENTORY_PROBE: '+sorted.join(','));
if(!sorted.length)throw new Error('BUSINESS_LEADS_INVENTORY_PROBE_FAILED: no lead/client lifecycle methods discovered; parser drifted');
throw new Error('BUSINESS_LEADS_INVENTORY_PROBE_PIN_REQUIRED: convert inventory into a reviewed executable regression gate before merge');
