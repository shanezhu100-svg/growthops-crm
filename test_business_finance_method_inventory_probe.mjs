import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_METHOD_INVENTORY_FAILED: dist/app missing');
const appFiles=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!appFiles.length)throw new Error('BUSINESS_FINANCE_METHOD_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle=appFiles.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const runtimeNames=new Set();
const methodPattern=/(?:^|[,\n])\s*(finance[A-Z][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
for(const match of bundle.matchAll(methodPattern))runtimeNames.add(match[1]);
if(!runtimeNames.size)throw new Error('BUSINESS_FINANCE_METHOD_INVENTORY_FAILED: no finance methods found; parser drifted');

const testFiles=fs.readdirSync(root)
  .filter(name=>/^test_business_finance_.*\.mjs$/.test(name))
  .filter(name=>name!=='test_business_finance_method_inventory_probe.mjs');
const mentioned=new Set();
const tokenPattern=/\b(finance[A-Z][A-Za-z0-9_$]*)\b/g;
for(const name of testFiles){
  const text=fs.readFileSync(path.join(root,name),'utf8');
  for(const match of text.matchAll(tokenPattern))mentioned.add(match[1]);
}
const all=[...runtimeNames].sort();
const uncovered=all.filter(name=>!mentioned.has(name));
console.log(`BUSINESS_FINANCE_METHOD_INVENTORY_OK: runtime=${all.length}; mentioned-in-tests=${all.length-uncovered.length}; uncovered=${uncovered.length}`);
console.log('BUSINESS_FINANCE_METHODS_ALL: '+all.join(','));
console.log('BUSINESS_FINANCE_METHODS_UNCOVERED: '+(uncovered.length?uncovered.join(','):'NONE'));
await import('./test_business_finance_cost_visibility_probe.mjs');
