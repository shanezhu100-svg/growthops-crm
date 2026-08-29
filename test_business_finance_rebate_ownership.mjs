import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_REBATE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_REBATE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extract(startMarker,endMarker,label){
  const start=bundle.indexOf(startMarker);
  if(start<0)throw new Error(`BUSINESS_FINANCE_REBATE_FAILED: final runtime ${label} implementation not found`);
  const end=bundle.indexOf(endMarker,start+startMarker.length);
  if(end<0)throw new Error(`BUSINESS_FINANCE_REBATE_FAILED: ${label} boundary marker not found`);
  return bundle.slice(start,end).replace(/,\s*$/,'').trim();
}

const policySource=extract('rebatePolicyForContact(contact,date=null){','contactCurrentRebateRate(contact){','rebatePolicyForContact');
const rateSource=extract('openingDealRebateRate(deal,date=null){','openingDealRebatePolicy(deal,date=null){','openingDealRebateRate');
const modeSource=extract('accountRebateMode(account){','accountRebateModeText(account){','accountRebateMode');
const effectiveStartSource=extract('openingDealEffectiveStart(deal){','openingDealAppliesToDate(deal,date){','openingDealEffectiveStart');
const appliesSource=extract('openingDealAppliesToDate(deal,date){','openingDealOwnerForRecord(clientId,platform,account,date){','openingDealAppliesToDate');
const ownerSource=extract('openingDealOwnerForRecord(clientId,platform,account,date){','openingDealOwnsRecord(deal,account,date){','openingDealOwnerForRecord');
const ownsSource=extract('openingDealOwnsRecord(deal,account,date){','openingDealSpendGroupsForPeriod(deal,period=this.openingSpendPeriod){','openingDealOwnsRecord');

const factorySource=`({
  openingDeals:[],
  localDateKey(){return '2026-08-29';},
  openingContact(deal){return deal?.contact||null;},
  openingDealMatchedAccounts(deal){return deal?.accounts||[];},
  ${policySource},
  ${rateSource},
  ${modeSource},
  ${effectiveStartSource},
  ${appliesSource},
  ${ownerSource},
  ${ownsSource}
})`;
let subject;
try{subject=vm.runInNewContext(factorySource,{Number,String,Array,Set},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_FINANCE_REBATE_FAILED: unable to execute final finance implementations: ${error.message}`);}
const assertEq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_FINANCE_REBATE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};

const contact={
  rebateRate:9,
  rebatePolicy:'legacy',
  rebatePolicies:[
    {effectiveDate:'2026-03-01',rebateRate:8,rebatePolicy:'March policy'},
    {effectiveDate:'2026-01-01',rebateRate:5,rebatePolicy:'January policy'},
  ],
};
assertEq(subject.rebatePolicyForContact(contact,'2025-12-31').rebateRate,0,'before first policy must not back-apply a future rebate');
assertEq(subject.rebatePolicyForContact(contact,'2026-02-28').rebateRate,5,'February uses latest already-effective policy');
assertEq(subject.rebatePolicyForContact(contact,'2026-03-01').rebateRate,8,'policy switches on exact effective date');
assertEq(subject.rebatePolicyForContact(contact,'2026-12-31').rebateRate,8,'latest policy remains effective after its start');
assertEq(subject.rebatePolicyForContact({rebateRate:6,rebatePolicy:'legacy-only'},'2026-05-01').rebateRate,6,'legacy contact without policy history preserves legacy rate');
assertEq(subject.openingDealRebateRate({contact},'2026-02-01'),5,'deal rebate rate delegates to date-effective contact policy');
assertEq(subject.openingDealRebateRate({contact},'2026-04-01'),8,'deal rebate rate switches with contact policy history');

const account={id:'acct-1',adAccountId:'A-1',rebateMode:'CHANNEL'};
const first={id:'deal-1',status:'OPENED',clientId:'client-1',platform:'FB',effectiveStartDate:'2026-01-01',effectiveEndDate:'',submitDate:'2025-12-20',accounts:[account]};
const newer={id:'deal-2',status:'OPENED',clientId:'client-1',platform:'FB',effectiveStartDate:'2026-03-01',effectiveEndDate:'',submitDate:'2026-02-20',accounts:[account]};
const inactive={id:'deal-3',status:'PREPARE',clientId:'client-1',platform:'FB',effectiveStartDate:'2026-04-01',effectiveEndDate:'',accounts:[account]};
subject.openingDeals=[first,newer,inactive];
assertEq(subject.openingDealOwnerForRecord('client-1','FB',account,'2026-02-15').id,'deal-1','record before newer start belongs to first opened deal');
assertEq(subject.openingDealOwnerForRecord('client-1','FB',account,'2026-03-01').id,'deal-2','newer effective deal takes ownership on its start date');
assertEq(subject.openingDealOwnerForRecord('client-1','FB',account,'2026-05-01').id,'deal-2','inactive later deal cannot steal ownership');
assertEq(subject.openingDealOwnerForRecord('client-1','TK',account,'2026-05-01'),null,'platform mismatch cannot own record');
assertEq(subject.openingDealOwnerForRecord('other-client','FB',account,'2026-05-01'),null,'client mismatch cannot own record');
assertEq(subject.openingDealOwnerForRecord('client-1','FB',{...account,rebateMode:'NONE'},'2026-05-01'),null,'no-rebate account cannot be attributed to a channel');
assertEq(subject.openingDealOwnsRecord(first,account,'2026-02-15'),true,'first deal owns pre-switch record');
assertEq(subject.openingDealOwnsRecord(first,account,'2026-03-15'),false,'first deal must not double-own record after newer deal wins');
assertEq(subject.openingDealOwnsRecord(newer,account,'2026-03-15'),true,'newer deal owns post-switch record');

console.log('BUSINESS_FINANCE_REBATE_OK: effective-policy-history+future-policy-deny+legacy-fallback+single-record-channel-ownership=executed');
