import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_OPENING_DEAL_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_OPENING_DEAL_PROBE_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['saveOpeningDeal','deleteOpeningDeal'];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
for(const name of names){
  console.log(`BUSINESS_OPENING_DEAL_PROBE_SOURCE_${name}=`+JSON.stringify(sources[name]));
  try{
    const single=vm.runInNewContext(`({${sources[name]}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
    if(typeof single[name]!=='function')throw new Error(`${name} not executable`);
    console.log(`BUSINESS_OPENING_DEAL_PROBE_COMPILE_${name}=OK`);
  }catch(error){
    throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} compile: ${error.message}`);
  }
}
console.log('BUSINESS_OPENING_DEAL_PROBE_OK: final-dist methods=saveOpeningDeal+deleteOpeningDeal; execution=compiled-only');
