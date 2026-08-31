import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_PROBE_FAILED: ${name} parser drifted`);
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
  financeReceivables:[],
  paymentTargetReceivable:null,
  paymentForm:{date:'2026-08-31',amount:'',method:'银行转账',account:'acct',note:''},
  assertMonthUnlocked(){return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},
  persist(){persists+=1;return true;},
  logAudit(){},
  notify(message,type){notifications.push({message:String(message??''),type:String(type??'')});},
});

function runCase(label,amount){
  notifications=[];
  persists=0;
  const row={
    id:`r-${label}`,
    clientId:'c1',
    amount:100,
    payments:[],
    currency:'USD',
    settlementMonth:'2026-08',
    dueDate:'2026-08-31',
    incomeType:'SERVICE_FEE',
  };
  subject.financeReceivables=[row];
  subject.paymentTargetReceivable=row;
  subject.paymentForm={date:'2026-08-31',amount,method:'银行转账',account:'acct',note:''};
  let threw='';
  try{subject.saveReceivablePayment();}catch(error){threw=String(error?.message||error);}
  return {
    input:String(amount),
    paymentCount:Array.isArray(row.payments)?row.payments.length:-1,
    paid:subject.financeReceivablePaid(row),
    unpaid:subject.financeReceivableUnpaid(row),
    persists,
    notifications:notifications.map(item=>`${item.type}:${item.message}`).join('|'),
    threw,
  };
}

const results={
  zero:runCase('zero','0'),
  negative:runCase('negative','-10'),
  nonnumeric:runCase('nonnumeric','abc'),
  over:runCase('over','100.01'),
  partial:runCase('partial','40'),
  exact:runCase('exact','100'),
};

throw new Error('BUSINESS_RECEIVABLE_PAYMENT_BOUNDS_PROBE: '+JSON.stringify(results));
