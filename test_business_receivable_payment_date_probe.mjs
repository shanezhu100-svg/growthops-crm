import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date,RegExp},{timeout:1000});

let uid=0;
let notifications=[];
let persists=0;
let monthKeys=[];
Object.assign(subject,{
  clients:[{id:'c1',name:'Alpha'}],
  financeReceivables:[],
  paymentTargetReceivable:null,
  paymentForm:{date:'',amount:'40',method:'银行转账',account:'acct',note:''},
  localDateKey(){return '2026-08-31';},
  assertMonthUnlocked(monthKey){monthKeys.push(String(monthKey));return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){persists+=1;return true;},
  logAudit(){},
  notify(message,type){notifications.push({message:String(message??''),type:String(type??'')});},
  financeReceivableClientName(){return 'Alpha';},
  financeIncomeTypeText(){return '投放服务费';},
  formatMoney(value,currency){return `${currency||'USD'}:${Number(value)}`;},
});

const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const includes=(actual,fragment,label)=>{if(!String(actual).includes(fragment))throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${label}; expected fragment=${fragment}; actual=${actual}`);};

function runCase(label,date){
  notifications=[];
  persists=0;
  monthKeys=[];
  const row={id:`r-${label}`,clientId:'c1',amount:100,payments:[],currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-31',incomeType:'SERVICE_FEE'};
  subject.financeReceivables=[row];
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date,amount:'40',method:'银行转账',account:'acct',note:''};
  subject.saveReceivablePayment();
  return {
    paymentCount:Array.isArray(row.payments)?row.payments.length:-1,
    paymentDate:Array.isArray(row.payments)&&row.payments.length?String(row.payments[0]?.date??''):'',
    persists,
    monthKeys:[...monthKeys],
    notifications:notifications.map(item=>item.message).join('|'),
  };
}

for(const [label,date] of [
  ['junk','abc'],
  ['short','2026-8-1'],
  ['impossibleDay','2026-02-30'],
  ['nonLeap','2026-02-29'],
  ['badMonth','2026-13-01'],
  ['zeroMonth','2026-00-10'],
  ['april31','2026-04-31'],
  ['trailing','2026-08-31x'],
]){
  const result=runCase(label,date);
  eq(result.paymentCount,0,`${label} invalid date must not create payment`);
  eq(result.persists,0,`${label} invalid date must not persist`);
  eq(result.monthKeys.length,0,`${label} invalid date must be denied before month-lock lookup`);
  includes(result.notifications,'请输入有效到账日期',`${label} invalid date notification`);
}

let result=runCase('empty','');
eq(result.paymentCount,1,'empty date must use local-date default and create payment');
eq(result.paymentDate,'2026-08-31','empty date local-date default');
eq(result.persists,1,'empty date valid payment persists once');
eq(JSON.stringify(result.monthKeys),JSON.stringify(['2026-08']),'empty date month-lock key');

result=runCase('valid','2026-08-30');
eq(result.paymentCount,1,'valid date creates payment');
eq(result.paymentDate,'2026-08-30','valid date preserved exactly');
eq(result.persists,1,'valid date persists once');
eq(JSON.stringify(result.monthKeys),JSON.stringify(['2026-08']),'valid date month-lock key');

result=runCase('leap','2028-02-29');
eq(result.paymentCount,1,'valid leap day creates payment');
eq(result.paymentDate,'2028-02-29','valid leap day preserved exactly');
eq(result.persists,1,'valid leap day persists once');
eq(JSON.stringify(result.monthKeys),JSON.stringify(['2028-02']),'valid leap-day month-lock key');

console.log('BUSINESS_RECEIVABLE_PAYMENT_DATE_OK: yyyy-mm-dd+calendar-valid=required; malformed+impossible=denied-before-month-lock+persist; empty=local-date-default; leap-day=accepted');
