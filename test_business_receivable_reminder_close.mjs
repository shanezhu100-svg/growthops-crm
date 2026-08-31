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

const names=['alertList','financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date},{timeout:1000});

let uid=0;
Object.assign(subject,{
  clients:[],financeReceivables:[],standaloneAlerts:[],dismissedAlerts:[],
  pushDueAlert(){},pushRechargeAlert(){},
  daysUntil(){return 1;},
  autoDueReminderStage(){return{reminderIndex:3,reminderTotal:3,reminderDaysBefore:1,reminderDate:'2026-08-29'};},
  alertTypeName(key){return key==='RECEIVABLE'?'应收回款提醒':key;},
  formatMoney(value,currency){return `${currency||'USD'}:${Number(value||0)}`;},
  financeIncomeTypeText(){return '投放服务费';},
  financeReceivableClientName(r){return this.clients.find(c=>String(c.id)===String(r?.clientId))?.name||'未知客户';},
  isAlertDismissed(){return false;},
  localDateKey(){return '2026-08-30';},
  assertMonthUnlocked(){return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){return true;},logAudit(){},notify(){},
});

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_RECEIVABLE_REMINDER_CLOSE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const has=(id)=>subject.alertList().some(item=>String(item.id)===String(id));
const ids=()=>subject.alertList().map(item=>String(item.id));
const client=(id,name)=>({id,name,archived:false,networkEnvironments:[],fbAccounts:[],tkAccounts:[]});
const bill=(id,clientId,amount=100,payments=[])=>({id,clientId,amount,payments,currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-30',incomeType:'SERVICE_FEE'});
const reminder=(id,overrides={})=>({id,typeKey:'RECEIVABLE',clientName:'Alpha',dueDate:'2026-08-30',cost:'',target:'',...overrides});

function reset(){
  subject.clients=[client('c1','Alpha'),client('c2','Beta')];
  subject.financeReceivables=[];
  subject.standaloneAlerts=[];
  subject.paymentTargetReceivable=null;
  subject.paymentForm={date:'2026-08-30',amount:'',method:'银行转账',account:'',note:''};
}
function pay(row,amount){
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date:'2026-08-30',amount,method:'银行转账',account:'acct',note:''};
  subject.saveReceivablePayment();
}

// Automatic bill reminder and a client-level standalone receivable reminder both
// remain while money is still outstanding. Recording a partial payment must not
// accidentally close either reminder.
reset();
let r1=bill('r1','c1');
subject.financeReceivables=[r1];
subject.standaloneAlerts=[reminder('sa-alpha'),{id:'sa-ip',typeKey:'IP',clientName:'Alpha',dueDate:'2026-08-30'}];
eq(has('RECEIVABLE-r1'),true,'automatic reminder exists before payment');
eq(has('sa-alpha'),true,'standalone receivable reminder exists before payment');
pay(r1,40);
eq(subject.financeReceivableUnpaid(r1),60,'partial payment leaves outstanding amount');
eq(has('RECEIVABLE-r1'),true,'automatic reminder remains after partial payment');
eq(has('sa-alpha'),true,'standalone reminder remains after partial payment');
eq(has('sa-ip'),true,'non-receivable reminder remains unchanged');

// The actual saveReceivablePayment path completing the outstanding balance must
// remove both the automatic bill reminder and the linked client-level reminder.
pay(r1,60);
eq(subject.financeReceivableUnpaid(r1),0,'full payment settles bill');
eq(has('RECEIVABLE-r1'),false,'automatic reminder closes after full payment');
eq(has('sa-alpha'),false,'linked standalone reminder closes after full payment');
eq(has('sa-ip'),true,'other reminder types remain after full payment');

// A client-level reminder represents the customer's outstanding receivables as a
// whole. Settling one bill must not close it while another bill is still unpaid.
reset();
r1=bill('r1','c1',100,[{amount:100}]);
let r2=bill('r2','c1',75,[]);
subject.financeReceivables=[r1,r2];
subject.standaloneAlerts=[reminder('sa-client',{clientId:'c1'})];
eq(has('sa-client'),true,'client reminder remains while another bill is outstanding');

// When a standalone reminder carries a precise receivableId, that exact bill is
// authoritative; another outstanding bill for the same client must not keep the
// already-settled bill reminder open.
subject.standaloneAlerts=[reminder('sa-r1',{clientId:'c1',receivableId:'r1'})];
eq(has('sa-r1'),false,'explicit settled receivable reminder closes independently');

// A different customer's outstanding reminder remains untouched.
subject.standaloneAlerts=[reminder('sa-beta',{clientId:'c2',clientName:'Beta'})];
subject.financeReceivables.push(bill('r3','c2',50,[]));
eq(has('sa-beta'),true,'different client outstanding reminder remains');

// Fail safe on unresolved linkage: duplicate names or a uniquely matched client
// with no receivable rows must not silently hide a manually created reminder.
reset();
subject.clients=[client('c1','Same'),client('c2','Same')];
subject.standaloneAlerts=[reminder('sa-ambiguous',{clientName:'Same'})];
eq(has('sa-ambiguous'),true,'ambiguous client name keeps reminder');
reset();
subject.standaloneAlerts=[reminder('sa-no-bill',{clientName:'Alpha'})];
eq(has('sa-no-bill'),true,'no linked receivable rows keeps reminder');

console.log('BUSINESS_RECEIVABLE_REMINDER_CLOSE_OK: full-payment=closes-linked; partial=preserved; other-outstanding=preserved; receivable-id=precise; unresolved=fail-safe; other-types=unchanged');
