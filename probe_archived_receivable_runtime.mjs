import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('ARCHIVED_RECEIVABLE_PROBE: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const defs=[...bundle.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm)];
const candidates=[];
for(let i=0;i<defs.length;i++){
  const name=defs[i][1];
  const start=defs[i].index+defs[i][0].indexOf(name);
  const end=i+1<defs.length?defs[i+1].index:bundle.length;
  const body=bundle.slice(start,end).replace(/\s+/g,' ').trim();
  if(/receiv|invoice|bill/i.test(name)||(/financeReceivables/.test(body)&&/(\.push\s*\(|\.splice\s*\(|\.unshift\s*\(|financeReceivables\s*=)/.test(body))){
    candidates.push({name,body:body.slice(0,900)});
  }
}
console.log('ARCHIVED_RECEIVABLE_PROBE_METHODS='+JSON.stringify(candidates));
const archiveMatches=[];
for(const re of [/archiv/ig,/归档/g,/isArchived/g,/clientStatus/g,/status\s*[:=]/g]){
  let m;
  while((m=re.exec(bundle))&&archiveMatches.length<30){
    archiveMatches.push(bundle.slice(Math.max(0,m.index-120),Math.min(bundle.length,m.index+220)).replace(/\s+/g,' '));
  }
}
console.log('ARCHIVED_RECEIVABLE_PROBE_STATUS='+JSON.stringify([...new Set(archiveMatches)]));
throw new Error('ARCHIVED_RECEIVABLE_PROBE_INTENTIONAL_STOP');
