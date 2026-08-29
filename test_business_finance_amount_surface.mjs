import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const anchor='openingDealSpendGroupsForPeriod(deal,period=this.openingSpendPeriod){';
const start=bundle.indexOf(anchor);
if(start<0)throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: openingDealSpendGroupsForPeriod not found');
const region=bundle.slice(start,start+24000);
const methods=[];
for(const match of region.matchAll(/(?:^|[,\n])\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)){
  const name=match[1];
  if(!methods.includes(name))methods.push(name);
  if(methods.length>=30)break;
}
if(methods.length<3)throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: method inventory parser drifted');
throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE: methods='+methods.join(','));
