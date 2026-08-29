import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_SETTLEMENT_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_SETTLEMENT_PROBE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_PROBE_FAILED: ${name} missing`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_PROBE_FAILED: ${name} boundary drift`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

for(const name of [
  'financeChannelMonthGroups',
  'financeExpectedRebateForChannelMonth',
  'financeClientExpectedRebateForChannelMonth',
  'financeSpendForChannelMonth',
  'financeClientSpendForChannelMonth',
  'financeActualRebateClientShare',
  'financeActualRebateGroups',
  'financeProfitGroups',
  'financeClientRow',
  'financeDefaultSettlementMonth',
  'defaultFinanceRebateForm',
  'normalizeFinanceActualRebates',
  'financeEntryProviderName',
  'financeEntryContactName',
  'financeEntryLinkedClientCount',
]){
  console.error(`BUSINESS_FINANCE_SETTLEMENT_FORMULA_START:${name}`);
  console.error(extractMethod(name));
  console.error(`BUSINESS_FINANCE_SETTLEMENT_FORMULA_END:${name}`);
}
throw new Error('BUSINESS_FINANCE_SETTLEMENT_FORMULA_PROBE_COMPLETE');
