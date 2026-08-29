import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_ANALYTICS_INVENTORY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_ANALYTICS_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const methodNames=new Set();
for(const match of bundle.matchAll(/(?:^|[,\n])\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm)){
  const name=match[1];
  if(/analytics|metric|kpi|summary|trend|chart/i.test(name))methodNames.add(name);
}
const identifierNames=new Set();
for(const match of bundle.matchAll(/\b([A-Za-z_$][A-Za-z0-9_$]*(?:Analytics|analytics|Kpi|KPI|Metric|metric|Trend|trend|Chart|chart)[A-Za-z0-9_$]*)\b/g))identifierNames.add(match[1]);
const methods=[...methodNames].sort();
const identifiers=[...identifierNames].sort();
if(!methods.length)throw new Error('BUSINESS_ANALYTICS_INVENTORY_FAILED: no analytics/metric/kpi/summary/trend/chart methods found');
throw new Error(`BUSINESS_ANALYTICS_INVENTORY_PIN_REQUIRED: methods=${methods.join(',')}; identifiers=${identifiers.slice(0,80).join(',')}`);
