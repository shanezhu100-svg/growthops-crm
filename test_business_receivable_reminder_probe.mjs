import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('RECEIVABLE_REMINDER_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('RECEIVABLE_REMINDER_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defs=[...bundle.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm)];
const keywords=['提醒','回款','应收','receiv','remind','overdue','due','todo','notice','alert','follow'];
const candidates=[];
for(let i=0;i<defs.length;i++){
  const name=defs[i][1];
  const start=defs[i].index+defs[i][0].indexOf(name);
  const end=i+1<defs.length?defs[i+1].index:bundle.length;
  const source=bundle.slice(start,end).trim();
  const low=source.toLowerCase();
  const hits=keywords.filter(k=>low.includes(k.toLowerCase()));
  if(!hits.length)continue;
  candidates.push({name,hits,source});
}
if(!candidates.length)throw new Error('RECEIVABLE_REMINDER_PROBE_FAILED: no reminder/receivable candidate methods found');
console.log('RECEIVABLE_REMINDER_PROBE_CANDIDATES='+candidates.map(c=>`${c.name}[${c.hits.join('|')}]`).join(','));
for(const candidate of candidates){
  if(!candidate.hits.some(k=>['提醒','回款','应收','remind','overdue','due','receiv'].includes(k)))continue;
  const compact=candidate.source.replace(/\s+/g,' ').slice(0,2400);
  console.log(`RECEIVABLE_REMINDER_PROBE_SOURCE ${candidate.name}: ${compact}`);
}
