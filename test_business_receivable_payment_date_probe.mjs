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
  const start=match.index+match[0].indexOf(match[1]),tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['financeReceivablePaid','financeReceivableUnpaid','saveReceivablePayment'];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date,RegExp,JSON,Set,Promise},{timeout:1000});

let uid=0,notifications=[],persists=0,barrierCalls=0,monthKeys=[];
Object.assign(subject,{
  clients:[{id:'c1',name:'Alpha'}],financeReceivables:[],auditLogs:[],paymentTargetReceivable:null,
  paymentForm:{date:'',amount:'40',method:'银行转账',account:'acct',note:''},
  localDateKey(){return '2026-08-31';},assertMonthUnlocked(monthKey){monthKeys.push(String(monthKey));return true;},
  accountUid(prefix){uid+=1;return `${prefix}-${uid}`;},persist(){persists+=1;return true;},
  persistReceivablePaymentBarrier:async()=>{barrierCalls+=1;},logAudit(){},
  notify(message,type){notifications.push({message:String(message??''),type:String(type??'')});},
  financeReceivableClientName(){return 'Alpha';},financeIncomeTypeText(){return '投放服务费';},formatMoney(value,currency){return `${currency||'USD'}:${Number(value)}`;},
});

const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const includes=(actual,fragment,label)=>{if(!String(actual).includes(fragment))throw new Error(`BUSINESS_RECEIVABLE_PAYMENT_DATE_FAILED: ${label}; expected fragment=${fragment}; actual=${actual}`);};

async function runCase(label,date){
  notifications=[];persists=0;barrierCalls=0;monthKeys=[];subject.auditLogs=[];
  const row={id:`r-${label}`,clientId:'c1',amount:100,payments:[],currency:'USD',settlementMonth:'2026-08',dueDate:'2026-08-31',incomeType:'SERVICE_FEE'};
  subject.financeReceivables=[row];subject.paymentTargetReceivable=row;
  subject.paymentForm={date,amount:'40',method:'银行转账',account:'acct',note:''};
  await subject.saveReceivablePayment();
  return {paymentCount:row.payments.length,paymentDate:row.payments.length?String(row.payments[0]?.date??''):'',persists,barrierCalls,monthKeys:[...monthKeys],notifications:notifications.map(item=>item.message).join('|')};
}

for(const [label,date] of [['junk','abc'],['short','2026-8-1'],['impossibleDay','2026-02-30'],['nonLeap','2026-02-29'],['badMonth','2026-13-01'],['zeroMonth','2026-00-10'],['april31','2026-04-31'],['trailing','2026-08-31x']]){
  const result=await runCase(label,date);
  eq(result.paymentCount,0,`${label} invalid date must not create payment`);eq(result.persists,0,`${label} invalid date must not persist`);eq(result.barrierCalls,0,`${label} invalid date must not cross ACK barrier`);eq(result.monthKeys.length,0,`${label} invalid date must be denied before month-lock lookup`);includes(result.notifications,'请输入有效到账日期',`${label} invalid date notification`);
}

for(const [label,date,expectedDate,month] of [['empty','','2026-08-31','2026-08'],['valid','2026-08-30','2026-08-30','2026-08'],['leap','2028-02-29','2028-02-29','2028-02']]){
  const result=await runCase(label,date);
  eq(result.paymentCount,1,`${label} valid date creates payment`);eq(result.paymentDate,expectedDate,`${label} payment date`);eq(result.persists,0,`${label} uses ACK barrier instead of debounced persist`);eq(result.barrierCalls,1,`${label} durable barrier count`);eq(JSON.stringify(result.monthKeys),JSON.stringify([month]),`${label} month-lock key`);
}

console.log('BUSINESS_RECEIVABLE_PAYMENT_DATE_OK: yyyy-mm-dd+calendar-valid=required; malformed+impossible=denied-before-month-lock+ACK; empty=local-date-default; leap-day=accepted; valid=durable-ACK');
