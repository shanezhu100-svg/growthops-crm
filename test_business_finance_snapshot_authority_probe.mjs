import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_COST_LOCK_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_COST_LOCK_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const re=/(?:^|[,\n])\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{/gm;
const hits=[...bundle.matchAll(re)];
const methods=[];
for(let i=0;i<hits.length;i++){
  const name=hits[i][1];
  const start=hits[i].index+hits[i][0].indexOf(name);
  const end=i+1<hits.length?hits[i+1].index:bundle.length;
  const source=bundle.slice(start,end).replace(/,\s*$/,'').trim();
  if(source.includes('financeCosts') && (/save|delete|remove|edit|cost/i.test(name)||source.includes('isMonthLocked'))) methods.push({name,source});
}
if(!methods.length)throw new Error('BUSINESS_FINANCE_COST_LOCK_PROBE_FAILED: no finance cost mutation candidates found');
for(const item of methods){
  console.log(`FINANCE_COST_LOCK_CANDIDATE ${item.name}: ${item.source.replace(/\s+/g,' ').slice(0,10000)}`);
}
throw new Error('BUSINESS_FINANCE_COST_LOCK_PROBE_EXPECTED_STOP: inspect mutation guards above, then remove this probe');
