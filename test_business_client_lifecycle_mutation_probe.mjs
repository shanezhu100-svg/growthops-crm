import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: no final app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['archiveClient','restoreClient','deleteLead'];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
let methods;
try{methods=vm.runInNewContext(`({${Object.values(sources).join(',\n')}})`,Object.create(null),{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: shipped methods not executable: ${error.message}`)}
for(const name of names)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE_FAILED: ${name} not executable`);

// Diagnostic-only, intentionally non-mergeable. Normalize whitespace so the CI log
// gives one compact line per actual shipped method; the follow-up replaces this probe
// with behavioral regression cases and removes the diagnostic file.
const compact=Object.fromEntries(Object.entries(sources).map(([name,source])=>[
  name,source.replace(/\s+/g,' ').trim()
]));
throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATION_PROBE: '+JSON.stringify(compact));
