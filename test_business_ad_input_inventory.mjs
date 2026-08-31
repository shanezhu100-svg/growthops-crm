import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AD_INPUT_INVENTORY_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

const methodRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(methodRe)];
function methodSource(name){
  for(let i=0;i<defs.length;i++){
    if(defs[i][1]!==name)continue;
    const start=defs[i].index+defs[i][0].indexOf(name);
    const end=i+1<defs.length?defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]):bundle.length;
    return bundle.slice(start,end).replace(/,\s*$/,'').trim();
  }
  throw new Error('BUSINESS_AD_INPUT_INVENTORY_FAILED: missing method '+name);
}
const metrics=methodSource('adDataDraftMetrics');
const save=methodSource('saveAdDataRecord');
const compact=s=>s.replace(/\s+/g,' ').trim();
throw new Error('BUSINESS_AD_INPUT_SOURCE: adDataDraftMetrics='+compact(metrics)+' || saveAdDataRecord='+compact(save));
