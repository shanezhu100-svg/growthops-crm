import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: no app-inline artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const strictSource=extractMethod('financeCompanySummaryCostGroups');
const textSource=extractMethod('financeCostText');
if(!strictSource.includes("['COMPANY','COMPANY_PROJECT']"))throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: strict scope allowlist drifted');
for(const forbidden of ['ALLOCATE_SERVICE','ALLOCATE_SPEND','financeCompanyNonClientCostGroups','financeActivePeriodSnapshot']){
  if(strictSource.includes(forbidden))throw new Error(`BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: strict authority contains forbidden dependency ${forbidden}`);
}
if(!textSource.includes('financeCompanySummaryCostGroups()'))throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: ALL card does not invoke strict authority method');
if(textSource.includes('financeCompanyNonClientCostGroups'))throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: ALL card still uses broad non-client authority');

const strictMethod=vm.runInNewContext(`({${strictSource}})`,{Number,String,Object,Array},{timeout:1000}).financeCompanySummaryCostGroups;
const textMethod=vm.runInNewContext(`({${textSource}})`,{Number,String,Object,Array},{timeout:1000}).financeCostText;
const subject={
  financeClientFilter:'ALL',
  financeCostGroups:{CNY:420},
  financeCompanyNonClientCostGroups:{CNY:120},
  financeActivePeriodSnapshot:{company:{companyPublicCostGroups:{CNY:999},companyProjectCostGroups:{CNY:999}}},
  financeCosts:[
    {date:'2026-09-01',scope:'COMPANY',amount:50,currency:'CNY'},
    {date:'2026-09-02',scope:'COMPANY_PROJECT',amount:30,currency:'CNY'},
    {date:'2026-09-03',scope:'ALLOCATE_SERVICE',amount:20,currency:'CNY'},
    {date:'2026-09-04',scope:'ALLOCATE_SPEND',amount:20,currency:'CNY'},
    {date:'2026-09-05',scope:'CLIENT',clientId:'c1',amount:300,currency:'CNY'},
    {date:'2026-10-01',scope:'COMPANY_PROJECT',amount:999,currency:'CNY'},
  ],
  financeDateMatch(date){return /^2026-09-/.test(String(date||''));},
  spendGroupsText(groups){return Object.entries(groups||{}).map(([cur,value])=>`${cur}:${value}`).join('|');},
};
subject.financeCompanySummaryCostGroups=function(){return strictMethod.call(subject);};
const strict=subject.financeCompanySummaryCostGroups();
if(JSON.stringify(strict)!==JSON.stringify({CNY:80}))throw new Error(`BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: strict total expected CNY 80, actual ${JSON.stringify(strict)}`);
if(textMethod.call(subject)!=='CNY:80')throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: ALL card did not exclude client/allocation costs from 420 fixture');
subject.financeClientFilter='c1';
if(textMethod.call(subject)!=='CNY:420')throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: selected-client cost behavior changed');

// Legacy locked-period fallback is safe only while source cost mutation remains
// fail-closed after month close. Keep those prerequisites mechanically guarded.
for(const [name,marker] of [
  ['saveFinanceCost','assertMonthUnlocked'],
  ['deleteFinanceCost','assertMonthUnlocked'],
  ['syncReceivableLinkedCost','isMonthLocked'],
  ['syncOpeningFeeCost','isMonthLocked'],
  ['ensureAutomaticAssetCosts','isMonthLocked'],
]){
  const source=extractMethod(name);
  if(!source.includes(marker))throw new Error(`BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: locked-month safety prerequisite drifted in ${name}`);
}

const registryPath=path.join(process.cwd(),'dist','vendor','vue-3.5.41.renders.js');
const registry=fs.readFileSync(registryPath,'utf8');
const copy='仅统计公司公共成本 + 公司项目成本；详细构成在下方成本模块查看。';
if(registry.split(copy).length-1!==1)throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: strict card copy missing or duplicated');
if(registry.includes('已包含公司成本 + 公司项目成本；详细构成在下方成本模块查看。'))throw new Error('BUSINESS_FINANCE_STRICT_COMPANY_COST_FAILED: broad company-cost copy remains');

console.log('BUSINESS_FINANCE_STRICT_COMPANY_COST_OK: total-card=COMPANY+COMPANY_PROJECT-only; client+service-allocation+spend-allocation=excluded; selected-client=preserved; locked-history-prerequisites=guarded');
