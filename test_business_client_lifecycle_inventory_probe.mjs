import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_LIFECYCLE_INVENTORY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_LIFECYCLE_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const methods=[];
const pattern=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{/gm;
for(const match of bundle.matchAll(pattern)){
  const name=match[1];
  if(/client|account|save|edit|form/i.test(name))methods.push(name);
}
const unique=[...new Set(methods)];
if(!unique.length)throw new Error('BUSINESS_CLIENT_LIFECYCLE_INVENTORY_FAILED: no candidate methods found; parser may have drifted');
console.log('BUSINESS_CLIENT_LIFECYCLE_INVENTORY: '+unique.join(','));
