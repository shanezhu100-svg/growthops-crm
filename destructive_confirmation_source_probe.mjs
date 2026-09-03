import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);if(!match)throw new Error(`missing ${name}`);
  const start=match.index+match[0].indexOf(match[1]),tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`parser drift ${name}`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);return tail.slice(0,next).replace(/,\s*$/,'').trim();
}
for(const name of ['deleteFinanceCost','deleteReceivablePayment','deleteReceivable','archiveClient','restoreClient','deleteLead','toggleFinanceMonthLock','voidReconciliation']){
  console.log(`DESTRUCTIVE_CONFIRM_SOURCE_BEGIN ${name}`);
  console.log(extractMethod(name));
  console.log(`DESTRUCTIVE_CONFIRM_SOURCE_END ${name}`);
}
