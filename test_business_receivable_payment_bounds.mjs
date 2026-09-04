import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment','deleteReceivablePayment','deleteReceivable'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date,JSON,Set,Promise},{timeout:1000});

let uid=0;
let notifications=[];
let persists=0;
let barrierCalls=0;
let audits=[];
let confirms=0;
let pendingConfirm=null;
let unlocked=true;
let lockedCostMonths=new Set();
Object.assign(subject,{
  clients:[{id:'c1',name:'Alpha'}],
  financeReceivables:[],
  financeCosts:[],
  auditLogs:[],
  receivableForm:null,
  paymentTargetReceivable:null,
  paymentForm:{date:'2026-08-31',amount:'',method:'银行转账',account:'acct',note:''},
  assertMonthUnlocked(){return unlocked;},
  isMonthLocked(month){return lockedCostMonths.has(String(month||''));},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){persists+=1;return true;},
  persistReceivablePaymentBarrier:async()=>{barrierCalls+=1;},
  persistReceivableBarrier:async()=>{barrierCalls+=1;},
  logAudit(action,detail){const row={action:String(action??''),detail:String(detail??'')};audits.push(row);subject.auditLogs.push(row);return row;},
  askConfirm(_options,callback){confirms+=1;pendingConfirm=Promise.resolve(callback());return pendingConfirm;},
  notify(message,type){notifications.push({message:String(message??''),type:String(type??'')});},
  financeReceivableClientName(){return 'Alpha';},
  financeIncomeTypeText(){return '投放服务费';},
  formatMoney(value,currency){return `${currency||'USD'}:${Number(value)}`;},
  normalizeReceivable(row){return {...row};},
  receivableLinkedCost(row){return this.financeCosts.find(cost=>cost.sourceType==='RECEIVABLE_ITEM'&&String(cost.sourceId)===String(row?.id))||null;},
});

const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const includes=(actual,fragment,label)=>{if(!String(actual).includes(fragment))throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${label}; expected fragment=${fragment}; actual=${actual}`);};

function resetMutationState(){
  notifications=[];
  persists=0;
  barrierCalls=0;
  audits=[];
  subject.auditLogs=[];
  confirms=0;
  pendingConfirm=null;
  unlocked=true;
  lockedCostMonths=new Set();
  subject.receivableForm=null;
}

async function runCase(label,amount){
  resetMutationState();
  const row={id:`r-${label}`,clientId:'c1',amount:100,payments:[],currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-31',incomeType:'SERVICE_FEE'};
  subject.financeReceivables=[row];
  subject.financeCosts=[];
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date:'2026-08-31',amount,method:'银行转账',account:'acct',note:''};
  await subject.saveReceivablePayment();
  return {
    row,
    paymentCount:Array.isArray(row.payments)?row.payments.length:-1,
    paymentAmount:Array.isArray(row.payments)&&row.payments.length?row.payments[0]?.amount:null,
    paid:subject.financeReceivablePaid(row),
    unpaid:subject.financeReceivableUnpaid(row),
    persists,
    barrierCalls,
    notifications:notifications.map(item=>item.message).join('|'),
  };
}

for(const [label,input] of [['zero','0'],['negative','-10'],['nonnumeric','abc'],['infinity','Infinity'],['negativeInfinity','-Infinity']]){
  const result=await runCase(label,input);
  eq(result.paymentCount,0,`${label} must not create payment`);
  eq(result.paid,0,`${label} must not increase paid amount`);
  eq(result.unpaid,100,`${label} must preserve unpaid amount`);
  eq(result.persists,0,`${label} must not persist`);
  eq(result.barrierCalls,0,`${label} must not cross durable barrier`);
  includes(result.notifications,'请输入有效回款金额',`${label} must use invalid-amount notification`);
}

let result=await runCase('over','100.01');
eq(result.paymentCount,0,'overpayment must not create payment');
eq(result.paid,0,'overpayment must not increase paid amount');
eq(result.unpaid,100,'overpayment must preserve unpaid amount');
eq(result.persists,0,'overpayment must not persist');
eq(result.barrierCalls,0,'overpayment must not cross durable barrier');
includes(result.notifications,'本次回款不能超过未收金额','overpayment notification preserved');

result=await runCase('partial','40');
eq(result.paymentCount,1,'partial payment must create one payment');
eq(result.paymentAmount,40,'partial payment amount preserved');
eq(result.paid,40,'partial payment paid total');
eq(result.unpaid,60,'partial payment unpaid total');
eq(result.persists,0,'partial payment uses ACK barrier instead of debounced persist');
eq(result.barrierCalls,1,'partial payment crosses durable barrier once');
includes(result.notifications,'回款流水已保存','partial payment success notification preserved');

result=await runCase('exact','100');
eq(result.paymentCount,1,'exact payment must create one payment');
eq(result.paymentAmount,100,'exact payment amount preserved');
eq(result.paid,100,'exact payment paid total');
eq(result.unpaid,0,'exact payment settles receivable');
eq(result.persists,0,'exact payment uses ACK barrier instead of debounced persist');
eq(result.barrierCalls,1,'exact payment crosses durable barrier once');
includes(result.notifications,'回款流水已保存','exact payment success notification preserved');

// Deleting one payment must recalculate paidAmount from the surviving ledger and
// acknowledge the accounting write before success. The edit form, when open on the
// same receivable, is refreshed from the canonical row.
resetMutationState();
let deleteRow={id:'r-delete-payment',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',payments:[
  {id:'pay-a',date:'2026-08-31',amount:40},{id:'pay-b',date:'2026-08-30',amount:20},
],paidAmount:60};
subject.financeReceivables=[deleteRow];
subject.financeCosts=[];
subject.receivableForm={id:deleteRow.id,paidAmount:999};
subject.deleteReceivablePayment(deleteRow,deleteRow.payments[0]);
await pendingConfirm;
eq(deleteRow.payments.length,1,'payment delete removes exactly one ledger row');
eq(deleteRow.payments[0].id,'pay-b','payment delete preserves unrelated ledger row');
eq(deleteRow.paidAmount,20,'payment delete recomputes paidAmount from surviving ledger');
eq(subject.receivableForm.paidAmount,20,'open receivable form refreshes after payment delete');
eq(confirms,1,'payment delete requires one confirmation');
eq(persists,0,'payment delete uses ACK barrier instead of debounced persist');
eq(barrierCalls,1,'payment delete crosses durable barrier once');
eq(audits.length,1,'payment delete audits once');
includes(notifications.map(item=>item.message).join('|'),'回款流水已删除','payment delete success notification preserved');

resetMutationState();
deleteRow={id:'r-delete-payment-locked',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',payments:[{id:'pay-lock',date:'2026-08-31',amount:25}],paidAmount:25};
subject.financeReceivables=[deleteRow];
unlocked=false;
subject.deleteReceivablePayment(deleteRow,deleteRow.payments[0]);
eq(deleteRow.payments.length,1,'locked payment month must preserve ledger');
eq(deleteRow.paidAmount,25,'locked payment month must preserve paidAmount');
eq(confirms,0,'locked payment delete must not open confirmation');
eq(persists,0,'locked payment delete must not persist');
eq(barrierCalls,0,'locked payment delete must not cross durable barrier');

// Receivables with any payment history are intentionally non-deletable. This is
// distinct from paidAmount compatibility: the canonical payment-ledger helper is
// authoritative and must block deletion before confirmation or cost cleanup.
resetMutationState();
let receivable={id:'r-with-payment',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',projectName:'August',payments:[{id:'p1',date:'2026-08-31',amount:1}]};
subject.financeReceivables=[receivable];
subject.financeCosts=[{id:'linked-keep',sourceType:'RECEIVABLE_ITEM',sourceId:receivable.id,date:'2026-08-01',amount:10}];
subject.deleteReceivable(receivable);
eq(subject.financeReceivables.length,1,'receivable with payment history must remain');
eq(subject.financeCosts.length,1,'blocked receivable delete must preserve linked cost');
eq(confirms,0,'receivable with payment history must not confirm deletion');
eq(persists,0,'receivable with payment history must not persist');
eq(barrierCalls,0,'receivable with payment history must not cross durable barrier');
includes(notifications.map(item=>item.message).join('|'),'已有回款流水','payment-history delete block notification preserved');

// A linked project cost in a locked accounting month independently blocks the
// receivable deletion even when the receivable itself has no payments.
resetMutationState();
receivable={id:'r-linked-cost-locked',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',projectName:'August',payments:[]};
subject.financeReceivables=[receivable];
subject.financeCosts=[{id:'linked-lock',sourceType:'RECEIVABLE_ITEM',sourceId:receivable.id,date:'2026-07-15',amount:10}];
lockedCostMonths.add('2026-07');
subject.deleteReceivable(receivable);
eq(subject.financeReceivables.length,1,'locked linked-cost month must preserve receivable');
eq(subject.financeCosts.length,1,'locked linked-cost month must preserve cost');
eq(confirms,0,'locked linked-cost delete must not confirm');
eq(persists,0,'locked linked-cost delete must not persist');
eq(barrierCalls,0,'locked linked-cost delete must not cross durable barrier');
includes(notifications.map(item=>item.message).join('|'),'关联项目成本所在月份已月结','linked-cost lock notification preserved');

// Successful receivable deletion is a separate durable mutation surface and must
// acknowledge the master-record write before announcing success.
resetMutationState();
receivable={id:'r-delete',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',projectName:'August',payments:[]};
const otherReceivable={id:'r-other',clientId:'c1',amount:50,currency:'USD',settlementMonth:'2026-08',incomeType:'OTHER',payments:[]};
subject.financeReceivables=[receivable,otherReceivable];
subject.financeCosts=[
  {id:'linked-delete',sourceType:'RECEIVABLE_ITEM',sourceId:receivable.id,date:'2026-08-01',amount:10},
  {id:'linked-other',sourceType:'RECEIVABLE_ITEM',sourceId:otherReceivable.id,date:'2026-08-01',amount:5},
  {id:'manual-cost',sourceType:'',sourceId:receivable.id,date:'2026-08-01',amount:7},
];
subject.deleteReceivable(receivable);
await pendingConfirm;
eq(subject.financeReceivables.length,1,'confirmed receivable delete removes exactly target row');
eq(subject.financeReceivables[0].id,'r-other','confirmed receivable delete preserves unrelated receivable');
eq(subject.financeCosts.some(cost=>cost.id==='linked-delete'),false,'confirmed receivable delete removes own linked generated cost');
eq(subject.financeCosts.some(cost=>cost.id==='linked-other'),true,'confirmed receivable delete preserves other receivable linked cost');
eq(subject.financeCosts.some(cost=>cost.id==='manual-cost'),true,'confirmed receivable delete preserves unrelated/manual cost');
eq(confirms,1,'confirmed receivable delete opens one confirmation');
eq(persists,0,'confirmed receivable delete uses ACK barrier instead of debounced persist');
eq(barrierCalls,1,'confirmed receivable delete crosses durable barrier once');
eq(audits.length,1,'confirmed receivable delete audits once');
includes(notifications.map(item=>item.message).join('|'),'收入项目及关联成本已删除','confirmed receivable delete success notification preserved');

resetMutationState();
receivable={id:'r-month-locked',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-08',incomeType:'SERVICE_FEE',payments:[]};
subject.financeReceivables=[receivable];
subject.financeCosts=[];
unlocked=false;
subject.deleteReceivable(receivable);
eq(subject.financeReceivables.length,1,'locked receivable month must preserve row');
eq(confirms,0,'locked receivable delete must not confirm');
eq(persists,0,'locked receivable delete must not persist');
eq(barrierCalls,0,'locked receivable delete must not cross durable barrier');

console.log('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_OK: finite-positive=required; overpayment=denied; payment-save+delete=ACK-aware; payment-delete=recalculates+lock-guarded; receivable-delete=payment+linked-lock-guarded+scoped-cost-cleanup+durable-ACK');
