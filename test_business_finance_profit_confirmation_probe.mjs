import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  'financeActualNetProfitGroups','financeExpectedNetProfitGroups','financeProfitBreakdownRows','financeProfitConfirmation',
  'financeActualProfitLabel','financeActualProfitNote','financeActualProfitText','financeExpectedProfitText',
  'financeActualNetProfitText','financeExpectedNetProfitText','financeConfirmedActualRebateGroups',
  'financeActualRebateGroupsForClientMonth','financeActualRebateText','financeExpectedRebateGroupsForClientMonth','financeExpectedRebateText'
];
for(const name of names){
  const source=extractMethod(name).replace(/\s+/g,' ').trim();
  console.log(`BUSINESS_FINANCE_PROFIT_METHOD_SOURCE ${name}: ${source}`);
}
console.log('BUSINESS_FINANCE_PROFIT_CONFIRMATION_PROBE_OK: implementations-extracted='+names.length);
