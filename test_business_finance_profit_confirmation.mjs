import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: final runtime ${name} implementation not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: ${name} boundary parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  'financeActualNetProfitGroups','financeExpectedNetProfitGroups','financeProfitBreakdownRows','financeProfitConfirmation',
  'financeActualProfitLabel','financeActualProfitNote','financeActualProfitText','financeExpectedProfitText',
  'financeActualNetProfitText','financeExpectedNetProfitText','financeConfirmedActualRebateGroups',
  'financeActualRebateGroupsForClientMonth','financeActualRebateText','financeExpectedRebateGroupsForClientMonth','financeExpectedRebateText'
];
const methods={};
for(const name of names){
  const object=vm.runInNewContext(`({${extractMethod(name)}})`,{Number,String,Object,Array,Math,Set},{timeout:1000});
  methods[name]=object[name];
  if(typeof methods[name]!=='function')throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: ${name} did not compile to a function`);
}
const call=(name,subject,...args)=>methods[name].call(subject,...args);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const mergeSpendGroups=(target,source)=>{for(const [currency,value] of Object.entries(source||{}))target[currency]=(target[currency]||0)+Number(value||0);return target;};
const subtractSpendGroups=(left,right)=>{const out={};for(const currency of new Set([...Object.keys(left||{}),...Object.keys(right||{})]))out[currency]=Number(left?.[currency]||0)-Number(right?.[currency]||0);return out;};

let subject={
  financeActiveSnapshotScope:null,
  financeReceivableTotals:{expected:{USD:100,CNY:10}},
  financeConfirmedActualRebateGroups:{USD:20,EUR:5},
  financeTotals:{expected:{USD:25,CNY:4}},
  financeCostGroups:{USD:30,CNY:2,EUR:1},
  mergeSpendGroups,subtractSpendGroups,
};
jsonEq(call('financeActualNetProfitGroups',subject),{USD:90,CNY:8,EUR:4},'actual net profit uses expected receivable + confirmed actual rebate - cost');
jsonEq(call('financeExpectedNetProfitGroups',subject),{USD:95,CNY:12,EUR:-1},'expected net profit uses expected receivable + expected rebate - cost');
subject.financeActiveSnapshotScope={actualNetProfitGroups:{USD:7},expectedNetProfitGroups:{CNY:8}};
const actualSnap=call('financeActualNetProfitGroups',subject),expectedSnap=call('financeExpectedNetProfitGroups',subject);
jsonEq(actualSnap,{USD:7},'actual snapshot overrides live arithmetic');
jsonEq(expectedSnap,{CNY:8},'expected snapshot overrides live arithmetic');
if(actualSnap===subject.financeActiveSnapshotScope.actualNetProfitGroups||expectedSnap===subject.financeActiveSnapshotScope.expectedNetProfitGroups)throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: snapshot groups must be defensive copies');

subject={
  financeReceivableTotals:{expected:{USD:100,EUR:10}},
  financeTotals:{expected:{CNY:5,EUR:3}},
  financeConfirmedActualRebateGroups:{USD:4,JPY:1},
  financeCostGroups:{USD:20,JPY:2},
  financeExpectedNetProfitGroups:{USD:80,CNY:5,EUR:13,JPY:-2},
  financeActualNetProfitGroups:{USD:84,EUR:10,JPY:-1},
  formatMoney(value,currency){return `${currency}:${Number(value||0).toFixed(2)}`;},
};
let rows=call('financeProfitBreakdownRows',subject,'EXPECTED');
jsonEq(rows.map(row=>row.currency),['USD','CNY','EUR','JPY'],'profit breakdown orders USD/CNY first then remaining currencies alphabetically');
jsonEq(rows.find(row=>row.currency==='USD'),{currency:'USD',receivable:100,rebate:0,cost:20,net:80,receivableText:'USD:100.00',rebateText:'USD:0.00',costText:'USD:20.00',netText:'USD:80.00'},'expected USD profit breakdown values and formatted text');
jsonEq(rows.find(row=>row.currency==='EUR'),{currency:'EUR',receivable:10,rebate:3,cost:0,net:13,receivableText:'EUR:10.00',rebateText:'EUR:3.00',costText:'EUR:0.00',netText:'EUR:13.00'},'expected EUR profit breakdown values');
rows=call('financeProfitBreakdownRows',subject,'ACTUAL');
jsonEq(rows.find(row=>row.currency==='JPY'),{currency:'JPY',receivable:0,rebate:1,cost:2,net:-1,receivableText:'JPY:0.00',rebateText:'JPY:1.00',costText:'JPY:2.00',netText:'JPY:-1.00'},'actual profit breakdown switches to confirmed rebate and actual net groups');
subject={financeReceivableTotals:{expected:{}},financeTotals:{expected:{}},financeConfirmedActualRebateGroups:{},financeCostGroups:{},financeExpectedNetProfitGroups:{},financeActualNetProfitGroups:{},formatMoney(value,currency){return `${currency}:${Number(value||0).toFixed(2)}`;}};
rows=call('financeProfitBreakdownRows',subject);
eq(rows.length,1,'empty profit breakdown still exposes one currency row');
eq(rows[0].currency,'USD','empty profit breakdown defaults to USD');

let captured=null;
subject={financeActivePeriodSnapshot:{id:'snap'},financeClientFilter:'ALL',financePeriodMonths(){return ['2026-09'];},financeReconciliationStatusForScope(){throw new Error('snapshot path must not call live reconciliation status');}};
jsonEq(call('financeProfitConfirmation',subject),{pendingReconciliations:0,unassignedSpendGroups:{},unassignedSpendTotal:0,allLocked:true,complete:true},'active period snapshot is always treated as complete and locked');
subject={financeActivePeriodSnapshot:null,financeClientFilter:'ALL',financePeriodMonths(){return ['2026-08','2026-09'];},financeReconciliationStatusForScope(client,months){captured=[client,months];return {complete:false,marker:'all'};}};
jsonEq(call('financeProfitConfirmation',subject),{complete:false,marker:'all'},'live ALL scope delegates to reconciliation authority');
jsonEq(captured,[null,['2026-08','2026-09']],'ALL scope passes null client and current period months');
subject.financeClientFilter='c7';subject.financeReconciliationStatusForScope=(client,months)=>{captured=[client,months];return {complete:true,marker:'client'};};
jsonEq(call('financeProfitConfirmation',subject),{complete:true,marker:'client'},'live client scope delegates to reconciliation authority');
jsonEq(captured,['c7',['2026-08','2026-09']],'client scope passes selected client id');

subject={financeProfitConfirmation:{allLocked:true,complete:true}};
eq(call('financeActualProfitLabel',subject),'已月结净利润','locked complete profit label');
subject.financeProfitConfirmation={allLocked:false,complete:true};
eq(call('financeActualProfitLabel',subject),'已确认净利润','confirmed unlocked profit label');
subject.financeProfitConfirmation={allLocked:false,complete:false};
eq(call('financeActualProfitLabel',subject),'当前净利润','incomplete profit label');
subject={financeProfitConfirmation:{allLocked:true,complete:true},spendGroupsText(){throw new Error('locked note must not format unassigned spend');}};
eq(call('financeActualProfitNote',subject),'当前核算周期已完成月结，利润数据已锁定。','locked profit note');
subject={financeProfitConfirmation:{allLocked:false,complete:true},spendGroupsText(){throw new Error('confirmed note must not format unassigned spend');}};
eq(call('financeActualProfitNote',subject),'当前范围需要返点的渠道均已完成对账，可视为已确认利润。','confirmed profit note');
subject={financeProfitConfirmation:{allLocked:false,complete:false,pendingReconciliations:2,unassignedSpendTotal:10,unassignedSpendGroups:{USD:9}},spendGroupsText(groups){return Object.entries(groups).map(([k,v])=>`${k}:${v}`).join('|');}};
eq(call('financeActualProfitNote',subject),'2 个渠道 / 币种待返点对账；存在未归属渠道消耗 USD:9，当前金额不是最终已确认利润。','incomplete note lists pending reconciliation and unassigned spend');
subject={financeProfitConfirmation:{allLocked:false,complete:false,pendingReconciliations:0,unassignedSpendTotal:0.01,unassignedSpendGroups:{}},spendGroupsText(){return 'unused';}};
eq(call('financeActualProfitNote',subject),'返点数据尚未完成确认，当前金额不是最终已确认利润。','incomplete fallback note at unassigned threshold');

subject={financeActualNetProfitText:'ACTUAL-TEXT',financeExpectedNetProfitText:'EXPECTED-TEXT'};
eq(call('financeActualProfitText',subject),'ACTUAL-TEXT','actual profit text delegates actual net-profit text');
eq(call('financeExpectedProfitText',subject),'EXPECTED-TEXT','expected profit text delegates expected net-profit text');
subject={financeActualNetProfitGroups:{USD:5},financeExpectedNetProfitGroups:{USD:6},spendGroupsText(groups){return Object.entries(groups).map(([k,v])=>`${k}:${v}`).join('|');}};
eq(call('financeActualNetProfitText',subject),'USD:5','actual net-profit text delegates grouped formatter');
eq(call('financeExpectedNetProfitText',subject),'USD:6','expected net-profit text delegates grouped formatter');

subject={financeActiveSnapshotScope:{actualRebateGroups:{USD:4}},financeClientFilter:'ALL',clients:[],financeReconciliations:[],financeSettlementMonthMatch(){return true;}};
const rebateSnap=call('financeConfirmedActualRebateGroups',subject);jsonEq(rebateSnap,{USD:4},'confirmed rebate snapshot override');if(rebateSnap===subject.financeActiveSnapshotScope.actualRebateGroups)throw new Error('BUSINESS_FINANCE_PROFIT_CONFIRMATION_FAILED: actual rebate snapshot must be copied');
subject={financeActiveSnapshotScope:null,financeClientFilter:'c1',clients:[{id:'c1',name:'Client'}],financeActualRebateGroups(client){return client.id==='c1'?{USD:7}:{};},financeReconciliations:[],financeSettlementMonthMatch(){return true;}};
jsonEq(call('financeConfirmedActualRebateGroups',subject),{USD:7},'selected client uses client actual rebate authority');
subject.financeClientFilter='missing';jsonEq(call('financeConfirmedActualRebateGroups',subject),{},'missing selected client yields empty actual rebate groups');
subject={financeActiveSnapshotScope:null,financeClientFilter:'ALL',clients:[],financeReconciliations:[
  {status:'DONE',settlementMonth:'2026-09',currency:'USD',actualRebate:10},
  {status:'DONE',settlementMonth:'2026-09',actualRebate:2},
  {status:'DONE',settlementMonth:'2026-09',currency:'CNY',actualRebate:3},
  {status:'VOID',settlementMonth:'2026-09',currency:'USD',actualRebate:999},
  {status:'DONE',settlementMonth:'2026-10',currency:'USD',actualRebate:999},
],financeSettlementMonthMatch(month){return String(month)==='2026-09';}};
jsonEq(call('financeConfirmedActualRebateGroups',subject),{USD:12,CNY:3},'ALL actual rebate excludes VOID/out-of-period and defaults currency to USD');
subject.spendGroupsText=groups=>Object.entries(groups).map(([k,v])=>`${k}:${v}`).join('|');subject.financeConfirmedActualRebateGroups={USD:12,CNY:3};
eq(call('financeActualRebateText',subject),'USD:12|CNY:3','actual rebate text delegates confirmed groups');

subject={financeReconciliations:[
  {id:'a',status:'DONE',settlementMonth:'2026-09',currency:'USD',share:5},
  {id:'b',status:'DONE',settlementMonth:'2026-09',currency:'CNY',share:-2},
  {id:'tiny',status:'DONE',settlementMonth:'2026-09',share:0.0000001},
  {id:'void',status:'VOID',settlementMonth:'2026-09',share:9},
  {id:'other-month',status:'DONE',settlementMonth:'2026-08',share:9},
],financeActualRebateClientShare(row){return Number(row.share||0);}};
jsonEq(call('financeActualRebateGroupsForClientMonth',subject,{id:'c1'},'2026-09'),{USD:5,CNY:-2},'client-month actual rebate filters VOID/month and ignores sub-threshold shares');

const client={id:'c1',fbAccounts:[{mode:'CHANNEL',adSpendCurrency:'USD',adDataRecords:[
  {date:'2026-09-01',currency:'USD',spend:100,rate:10},
  {date:'2026-09-02',spend:50,rate:20},
  {date:'2026-08-31',currency:'USD',spend:999,rate:10},
]}],tkAccounts:[{mode:'CHANNEL',adSpendCurrency:'CNY',adDataRecords:[{date:'2026-09-03',currency:'CNY',spend:200,rate:5}]},{mode:'NONE',adSpendCurrency:'USD',adDataRecords:[{date:'2026-09-04',spend:999,rate:99}]}]};
subject={accountRebateMode(account){return account.mode;},openingDealOwnerForRecord(clientId,platform,account,rowDate){const record=account.adDataRecords.find(r=>r.date===rowDate);return record?.noOwner?null:{rate:record?.rate||0};},openingDealRebateRate(owner){return owner.rate;}};
jsonEq(call('financeExpectedRebateGroupsForClientMonth',subject,null,'2026-09'),{},'null client has no expected rebate');
jsonEq(call('financeExpectedRebateGroupsForClientMonth',subject,client,'2026-09'),{USD:20,CNY:10},'expected rebate uses CHANNEL records in target month, account currency fallback, and dated deal rate');
subject={financeTotals:{expected:{USD:20}},spendGroupsText(groups){return Object.entries(groups).map(([k,v])=>`${k}:${v}`).join('|');}};
eq(call('financeExpectedRebateText',subject),'USD:20','expected rebate text delegates expected totals');

console.log('BUSINESS_FINANCE_PROFIT_CONFIRMATION_OK: snapshot+net-profit+breakdown+confirmation+labels+notes+actual-expected-rebate=executed');
