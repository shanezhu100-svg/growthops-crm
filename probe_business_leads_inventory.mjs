import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_LEADS_INVENTORY_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEADS_INVENTORY_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_LEADS_INVENTORY_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const targets=[
  'defaultLeadForm','saveLead','convertLeadToClient','openConvertedLeadClient','deleteLead','leadStats','filteredLeads',
  'normalizeClient','saveClient','ensureClientFirstReceivable','archiveClient','restoreClient','deleteClient'
];
for(const name of targets){
  const source=extractMethod(name);
  console.log(`BUSINESS_LEADS_METHOD_BEGIN:${name}`);
  console.log(source);
  console.log(`BUSINESS_LEADS_METHOD_END:${name}`);
}
throw new Error('BUSINESS_LEADS_INVENTORY_PROBE_PIN_REQUIRED: replace source probe with executable lifecycle assertions before merge');
