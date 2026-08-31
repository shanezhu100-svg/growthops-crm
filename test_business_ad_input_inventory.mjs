import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AD_INPUT_INVENTORY_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_AD_INPUT_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const methodRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(methodRe)];
const hits=[];
for(let i=0;i<defs.length;i++){
  const name=defs[i][1];
  const start=defs[i].index+defs[i][0].indexOf(name);
  const end=i+1<defs.length?defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]):bundle.length;
  const source=bundle.slice(start,end);
  if(!/adData(?:Draft|Records)/.test(source))continue;
  const fields=[...new Set([...source.matchAll(/(?:adDataDraft|record)\.([A-Za-z_$][A-Za-z0-9_$]*)/g)].map(m=>m[1]))].sort();
  const mutations=[];
  for(const marker of ['adDataRecords.push','adDataRecords.splice','adDataRecords=','persist(','logAudit(','notify(']){
    if(source.includes(marker))mutations.push(marker.replace('(', '').replace('=', '=assign'));
  }
  hits.push({name,fields,mutations,bytes:source.length});
}
if(!hits.length)throw new Error('BUSINESS_AD_INPUT_INVENTORY_FAILED: no methods referencing adDataDraft/adDataRecords');
const persistence=hits.filter(x=>x.mutations.some(m=>/push|splice|assign|persist|logAudit/.test(m)));
const fieldSet=[...new Set(hits.flatMap(x=>x.fields))].sort();
throw new Error(
  'BUSINESS_AD_INPUT_INVENTORY: methods='+hits.map(x=>`${x.name}[${x.mutations.join('+')||'read'}]`).join(',')+
  '; persistence='+persistence.map(x=>x.name).join(',')+
  '; fields='+fieldSet.join(',')
);
