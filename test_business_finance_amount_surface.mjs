import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: ${name} start missing`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const definitions=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(definitions.length<2||definitions[0][1]!==name){
    throw new Error(`BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: ${name} next-method parser drifted`);
  }
  const nextStart=definitions[1].index+definitions[1][0].indexOf(definitions[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const targets=[
  'openingDealSpendGroupsForPeriod',
  'openingDealRebateText',
  'openingDealsFinancialsForPeriod',
  'financeAdSpendGroups',
  'financeReceivableGroupsForClientMonth',
  'financeServiceFeeReceivableGroupsForClientMonth',
  'financeDealsFinancials',
];
for(const label of targets){
  console.error(`BUSINESS_FINANCE_FORMULA_PROBE_START:${label}`);
  console.error(extractMethod(label));
  console.error(`BUSINESS_FINANCE_FORMULA_PROBE_END:${label}`);
}
throw new Error('BUSINESS_FINANCE_FORMULA_PROBE_COMPLETE');
