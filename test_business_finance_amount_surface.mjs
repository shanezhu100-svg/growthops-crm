import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extract(startMarker,endMarker,label){
  const start=bundle.indexOf(startMarker);
  if(start<0)throw new Error(`BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: ${label} start missing`);
  const end=bundle.indexOf(endMarker,start+startMarker.length);
  if(end<0)throw new Error(`BUSINESS_FINANCE_AMOUNT_SURFACE_PROBE_FAILED: ${label} end missing`);
  return bundle.slice(start,end).replace(/,\s*$/,'').trim();
}

const targets=[
  ['openingDealSpendGroupsForPeriod(deal,period=this.openingSpendPeriod){','openingDealSpendGroups(deal){','openingDealSpendGroupsForPeriod'],
  ['openingDealRebateText(deal){','openingDealsFinancialsForPeriod(period=this.openingSpendPeriod){','openingDealRebateText'],
  ['openingDealsFinancialsForPeriod(period=this.openingSpendPeriod){','openingDealsSpendGroupsUniqueForPeriod(period=this.openingSpendPeriod){','openingDealsFinancialsForPeriod'],
  ['financeAdSpendGroups(client,monthsOverride=null){','financeClientAdSpendGroups(client,monthsOverride=null){','financeAdSpendGroups'],
  ['financeReceivableGroupsForClientMonth(client,month){','financeServiceFeeReceivableGroupsForClientMonth(client,month){','financeReceivableGroupsForClientMonth'],
  ['financeServiceFeeReceivableGroupsForClientMonth(client,month){','financePeriodMonths(){','financeServiceFeeReceivableGroupsForClientMonth'],
  ['financeDealsFinancials(deals){','financeChannelDeals(channel){','financeDealsFinancials'],
];
for(const [start,end,label] of targets){
  console.error(`BUSINESS_FINANCE_FORMULA_PROBE_START:${label}`);
  console.error(extract(start,end,label));
  console.error(`BUSINESS_FINANCE_FORMULA_PROBE_END:${label}`);
}
throw new Error('BUSINESS_FINANCE_FORMULA_PROBE_COMPLETE');
