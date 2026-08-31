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

const names=['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date},{timeout:1000});

let uid=0;
let notifications=[];
let persists=0;
Object.assign(subject,{
  clients:[{id:'c1',name:'Alpha'}],
  financeReceivables:[],
  paymentTargetReceivable:null,
  paymentForm:{date:'2026-08-31',amount:'',method:'银行转账',account:'acct',note:''},
  assertMonthUnlocked(){return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){persists+=1;return true;},
  logAudit(){},
  notify(message,type){notifications.push({message:String(message??''),type:String(type??'')});},
  financeReceivableClientName(){return 'Alpha';},
  financeIncomeTypeText(){return '投放服务费';},
  formatMoney(value,currency){return `${currency||'USD'}:${Number(value)}`;},
});

const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const includes=(actual,fragment,label)=>{if(!String(actual).includes(fragment))throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_FAILED: ${label}; expected fragment=${fragment}; actual=${actual}`);};

function runCase(label,amount){
  notifications=[];
  persists=0;
  const row={id:`r-${label}`,clientId:'c1',amount:100,payments:[],currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-31',incomeType:'SERVICE_FEE'};
  subject.financeReceivables=[row];
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date:'2026-08-31',amount,method:'银行转账',account:'acct',note:''};
  subject.saveReceivablePayment();
  return {
    row,
    paymentCount:Array.isArray(row.payments)?row.payments.length:-1,
    paymentAmount:Array.isArray(row.payments)&&row.payments.length?row.payments[0]?.amount:null,
    paid:subject.financeReceivablePaid(row),
    unpaid:subject.financeReceivableUnpaid(row),
    persists,
    notifications:notifications.map(item=>item.message).join('|'),
  };
}

for(const [label,input] of [['zero','0'],['negative','-10'],['nonnumeric','abc'],['infinity','Infinity'],['negativeInfinity','-Infinity']]){
  const result=runCase(label,input);
  eq(result.paymentCount,0,`${label} must not create payment`);
  eq(result.paid,0,`${label} must not increase paid amount`);
  eq(result.unpaid,100,`${label} must preserve unpaid amount`);
  eq(result.persists,0,`${label} must not persist`);
  includes(result.notifications,'请输入有效回款金额',`${label} must use invalid-amount notification`);
}

let result=runCase('over','100.01');
eq(result.paymentCount,0,'overpayment must not create payment');
eq(result.paid,0,'overpayment must not increase paid amount');
eq(result.unpaid,100,'overpayment must preserve unpaid amount');
eq(result.persists,0,'overpayment must not persist');
includes(result.notifications,'本次回款不能超过未收金额','overpayment notification preserved');

result=runCase('partial','40');
eq(result.paymentCount,1,'partial payment must create one payment');
eq(result.paymentAmount,40,'partial payment amount preserved');
eq(result.paid,40,'partial payment paid total');
eq(result.unpaid,60,'partial payment unpaid total');
eq(result.persists,1,'partial payment persists once');
includes(result.notifications,'回款流水已保存','partial payment success notification preserved');

result=runCase('exact','100');
eq(result.paymentCount,1,'exact payment must create one payment');
eq(result.paymentAmount,100,'exact payment amount preserved');
eq(result.paid,100,'exact payment paid total');
eq(result.unpaid,0,'exact payment settles receivable');
eq(result.persists,1,'exact payment persists once');
includes(result.notifications,'回款流水已保存','exact payment success notification preserved');

console.log('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_OK: finite-positive=required; zero+negative+nan+infinity=denied; overpayment=denied; partial+exact=preserved');
