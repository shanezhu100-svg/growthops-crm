import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['_legacyAlertList','financeReceivableCollectionNodes','financeReceivableCollectionAllocation','financeReceivableBuildCollectionNodes','alertList','financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date,JSON,Set,Promise},{timeout:1000});

let uid=0;
Object.assign(subject,{
  clients:[],financeReceivables:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[],_activeReminderDates:null,
  pushDueAlert(){},pushRechargeAlert(){},
  daysUntil(){return 1;},
  autoDueReminderStage(date){if(this._activeReminderDates&&!this._activeReminderDates.has(String(date)))return null;return{reminderIndex:3,reminderTotal:3,reminderDaysBefore:1,reminderDate:'2026-08-29'};},
  alertTypeName(key){return key==='RECEIVABLE'?'应收回款提醒':key;},
  formatMoney(value,currency){return `${currency||'USD'}:${Number(value||0)}`;},
  financeIncomeTypeText(){return '投放服务费';},
  financeReceivableClientName(r){return this.clients.find(c=>String(c.id)===String(r?.clientId))?.name||'未知客户';},
  isAlertDismissed(){return false;},
  localDateKey(){return '2026-08-30';},
  assertMonthUnlocked(){return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){return true;},persistReceivablePaymentBarrier:async()=>{},logAudit(){},notify(){},
});

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const has=(id)=>subject.alertList().some(item=>String(item.id)===String(id));
const client=(id,name)=>({id,name,archived:false,networkEnvironments:[],fbAccounts:[],tkAccounts:[]});
const bill=(id,clientId,amount=100,payments=[])=>({id,clientId,amount,payments,currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-30',incomeType:'SERVICE_FEE'});
const reminder=(id,overrides={})=>({id,typeKey:'RECEIVABLE',clientName:'Alpha',dueDate:'2026-08-30',cost:'',target:'',...overrides});

function reset(){
  subject.clients=[client('c1','Alpha'),client('c2','Beta')];
  subject.financeReceivables=[];
  subject.standaloneAlerts=[];
  subject.auditLogs=[];
  subject._activeReminderDates=null;
  subject.paymentTargetReceivable=null;
  subject.paymentForm={date:'2026-08-30',amount:'',method:'银行转账',account:'',note:''};
}
async function pay(row,amount){
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date:'2026-08-30',amount,method:'银行转账',account:'acct',note:''};
  await subject.saveReceivablePayment();
}

// Formal financeReceivables are the single reminder authority once a standalone
// RECEIVABLE can be linked. While money is outstanding, keep only the automatic
// bill reminder and suppress the duplicate client-level standalone reminder.
reset();
let r1=bill('r1','c1');
subject.financeReceivables=[r1];
subject.standaloneAlerts=[reminder('sa-alpha'),{id:'sa-ip',typeKey:'IP',clientName:'Alpha',dueDate:'2026-08-30'}];
eq(has('RECEIVABLE-r1'),true,'automatic reminder exists before payment');
eq(has('sa-alpha'),false,'linked standalone reminder suppressed before payment');
eq(has('sa-ip'),true,'non-receivable reminder remains unchanged');
await pay(r1,40);
eq(subject.financeReceivableUnpaid(r1),60,'partial payment leaves outstanding amount');
eq(has('RECEIVABLE-r1'),true,'automatic reminder remains after partial payment');
eq(has('sa-alpha'),false,'linked standalone reminder stays suppressed after partial payment');
eq(has('sa-ip'),true,'non-receivable reminder remains unchanged after partial payment');

// Completing the outstanding balance removes the automatic bill reminder. The
// linked standalone reminder stays suppressed, so settled receivables never reappear.
await pay(r1,60);
eq(subject.financeReceivableUnpaid(r1),0,'full payment settles bill');
eq(has('RECEIVABLE-r1'),false,'automatic reminder closes after full payment');
eq(has('sa-alpha'),false,'linked standalone reminder remains suppressed after full payment');
eq(has('sa-ip'),true,'other reminder types remain after full payment');

// A client with multiple receivables must still have exactly the unpaid automatic
// bill reminder(s), never an additional client-level RECEIVABLE reminder.
reset();
r1=bill('r1','c1',100,[{amount:100}]);
let r2=bill('r2','c1',75,[]);
subject.financeReceivables=[r1,r2];
subject.standaloneAlerts=[reminder('sa-client',{clientId:'c1'})];
eq(has('RECEIVABLE-r1'),false,'settled bill has no automatic reminder');
eq(has('RECEIVABLE-r2'),true,'other unpaid bill keeps its automatic reminder');
eq(has('sa-client'),false,'client-level standalone reminder suppressed when formal receivables exist');

// A precise receivableId is also subordinate to the formal row, regardless of
// whether that row is settled or still outstanding.
subject.standaloneAlerts=[reminder('sa-r1',{clientId:'c1',receivableId:'r1'})];
eq(has('sa-r1'),false,'explicit settled receivable standalone reminder suppressed');
subject.standaloneAlerts=[reminder('sa-r2',{clientId:'c1',receivableId:'r2'})];
eq(has('RECEIVABLE-r2'),true,'explicit unpaid receivable keeps automatic reminder');
eq(has('sa-r2'),false,'explicit unpaid receivable standalone reminder suppressed');

// A different customer's formal outstanding receivable follows the same rule.
subject.standaloneAlerts=[reminder('sa-beta',{clientId:'c2',clientName:'Beta'})];
subject.financeReceivables.push(bill('r3','c2',50,[]));
eq(has('RECEIVABLE-r3'),true,'different client automatic reminder remains');
eq(has('sa-beta'),false,'different client linked standalone reminder suppressed');

// Fail safe on unresolved linkage: duplicate names or a uniquely matched client
// with no formal receivable rows must not silently hide a manually created reminder.
reset();
subject.clients=[client('c1','Same'),client('c2','Same')];
subject.standaloneAlerts=[reminder('sa-ambiguous',{clientName:'Same'})];
eq(has('sa-ambiguous'),true,'ambiguous client name keeps reminder');
reset();
subject.standaloneAlerts=[reminder('sa-no-bill',{clientName:'Alpha'})];
eq(has('sa-no-bill'),true,'no linked receivable rows keeps reminder');

// Collection nodes split one monthly accounting receivable into independently due
// collection obligations. A future month-end node must not inflate the 15th reminder.
reset();
const split=bill('split','c1',2000,[]);
split.settlementMonth='2026-09';
split.dueDate='2026-09-15';
split.collectionNodes=[
  {id:'2026-09-D15',dueDate:'2026-09-15',amount:1000,label:'15日收款'},
  {id:'2026-09-EOM',dueDate:'2026-09-30',amount:1000,label:'月末收款'},
];
subject.financeReceivables=[split];
subject._activeReminderDates=new Set(['2026-09-15']);
let alerts=subject.alertList();
eq(alerts.some(a=>String(a.id)==='RECEIVABLE-split'),false,'split master reminder suppressed');
eq(alerts.some(a=>String(a.id)==='RECEIVABLE-split::COLLECTION::2026-09-D15'),true,'15th node reminder shown');
eq(alerts.some(a=>String(a.id)==='RECEIVABLE-split::COLLECTION::2026-09-EOM'),false,'future month-end node excluded');
eq(alerts.filter(a=>String(a.id).startsWith('RECEIVABLE-split::COLLECTION::')).length,1,'only current collection node shown');

// Existing payment history is allocated deterministically to the earliest due node.
split.payments=[{id:'p1',amount:600}];
let allocation=subject.financeReceivableCollectionAllocation(split);
eq(allocation['2026-09-D15'],600,'partial receipt allocated to first node');
eq(allocation['2026-09-EOM'],0,'future node receives no allocation before first is settled');
split.payments=[{id:'p1',amount:1000}];
allocation=subject.financeReceivableCollectionAllocation(split);
eq(allocation['2026-09-D15'],1000,'first node fully settled');
eq(allocation['2026-09-EOM'],0,'second node untouched after exact first-node receipt');
subject._activeReminderDates=new Set(['2026-09-15','2026-09-30']);
alerts=subject.alertList();
eq(alerts.some(a=>String(a.id)==='RECEIVABLE-split::COLLECTION::2026-09-D15'),false,'settled first node closes');
eq(alerts.some(a=>String(a.id)==='RECEIVABLE-split::COLLECTION::2026-09-EOM'),true,'month-end node opens when its reminder window arrives');

// More cash continues earliest-due-first and leaves only the true balance on the
// second node; this keeps audit/reconciliation deterministic without rewriting old payments.
split.payments=[{id:'p1',amount:1500}];
allocation=subject.financeReceivableCollectionAllocation(split);
eq(allocation['2026-09-D15'],1000,'first node remains fully allocated');
eq(allocation['2026-09-EOM'],500,'excess receipt flows to second node');

// Invalid explicit schedules fail safe to the original monthly receivable instead
// of hiding money: node totals must equal the master amount and dates must be valid.
reset();
const invalid=bill('invalid','c1',2000,[]);
invalid.collectionNodes=[{id:'bad-1',dueDate:'2026-08-15',amount:900},{id:'bad-2',dueDate:'2026-08-30',amount:1000}];
subject.financeReceivables=[invalid];
eq(subject.financeReceivableCollectionNodes(invalid).length,0,'invalid node total rejected');
eq(has('RECEIVABLE-invalid'),true,'invalid node plan falls back to master reminder');

// Semi-monthly plan construction is currency-stable and calendar-aware.
const built=subject.financeReceivableBuildCollectionNodes({amount:2000,settlementMonth:'2026-09'},{mode:'SEMI_MONTHLY',firstDay:15,firstRatio:0.5});
eq(built.length,2,'semi-monthly node count');
eq(built[0].dueDate,'2026-09-15','semi-monthly first date');
eq(built[0].amount,1000,'semi-monthly first amount');
eq(built[1].dueDate,'2026-09-30','semi-monthly month-end date');
eq(built[1].amount,1000,'semi-monthly second amount');
const leap=subject.financeReceivableBuildCollectionNodes({amount:99.99,settlementMonth:'2028-02'},{mode:'SEMI_MONTHLY'});
eq(leap[1].dueDate,'2028-02-29','leap-year month end');
eq(Math.round((leap[0].amount+leap[1].amount)*100)/100,99.99,'rounded node sum equals master');

console.log('BUSINESS_RECEIVABLE_REMINDER_CLOSE_OK: formal-receivable=single-authority; linked-standalone=suppressed; legacy=compatible; collection-nodes=current-window-only+master-suppressed; payments=earliest-due-allocation; invalid-plan=master-fail-safe; semi-monthly=15th+month-end; settled=closed; payment=ACK-aware');
