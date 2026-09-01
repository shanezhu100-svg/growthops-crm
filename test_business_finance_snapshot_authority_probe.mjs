import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_SNAPSHOT_AUTHORITY_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_SNAPSHOT_AUTHORITY_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function methodSources(){
  const re=/(?:^|[,\n])\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{/gm;
  const hits=[...bundle.matchAll(re)];
  const out=[];
  for(let i=0;i<hits.length;i++){
    const name=hits[i][1];
    const start=hits[i].index+hits[i][0].indexOf(name);
    const end=i+1<hits.length?hits[i+1].index:bundle.length;
    out.push({name,source:bundle.slice(start,end).replace(/,\s*$/,'').trim()});
  }
  return out;
}

const methods=methodSources();
const candidates=methods.filter(({name,source})=>
  name.startsWith('finance') && (
    source.includes('financeMonthSnapshots') ||
    source.includes('companyProjectCostGroups') ||
    source.includes('companyPublicCostGroups') ||
    /snapshot/i.test(name)
  )
);
if(!candidates.length)throw new Error('BUSINESS_FINANCE_SNAPSHOT_AUTHORITY_PROBE_FAILED: no finance month-snapshot candidates found');
for(const item of candidates){
  const compact=item.source.replace(/\s+/g,' ');
  console.log(`FINANCE_SNAPSHOT_AUTHORITY_CANDIDATE ${item.name}: ${compact.slice(0,8000)}`);
}
throw new Error('BUSINESS_FINANCE_SNAPSHOT_AUTHORITY_PROBE_EXPECTED_STOP: inspect month snapshot methods above, then remove this probe');
