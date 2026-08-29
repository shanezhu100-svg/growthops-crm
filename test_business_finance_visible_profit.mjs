import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=['financeVisibleReceivables','financeReceivableClientName','financeReceivableIncomeBreakdownText','financeProfitPagedRows','financeProfitTotalPages'];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
function makeSubject(){
  const factory=`({
    financeReceivables:[], clients:[], financeClientFilter:'ALL', receivableOwnerFilter:'ALL', receivableLedgerMode:'ALL', receivableIncomeTypeFilter:'ALL', receivableStatusFilter:'ALL',
    financeRows:[], profitPageStart:0, profitPageEnd:10, profitPageSize:10,
    financeSettlementMonthMatch(month){return ['2026-08','2026-09'].includes(String(month||''));},
    financeReceivableUnpaid(row){return Number(row?.unpaid||0);},
    financeReceivableStatusKey(row){return row?.statusKey||'PENDING';},
    financeIncomeTypeText(type){return ({SERVICE_FEE:'服务费',REBATE:'返点',OTHER:'其他收入'})[type]||String(type);},
    ${names.map(name=>sources[name]).join(',\n    ')}
  })`;
  try{return vm.runInNewContext(factory,{Number,String,Object,Array,Math},{timeout:1000});}
  catch(error){throw new Error(`BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: unable to execute final implementations: ${error.message}`);}
}
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_VISIBLE_PROFIT_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};

let subject=makeSubject();
subject.financeReceivables=[
  {id:'aug-late',settlementMonth:'2026-08',clientId:'c1',ownerType:'CLIENT',incomeType:'SERVICE_FEE',statusKey:'PENDING',unpaid:100,dueDate:'2026-08-20'},
  {id:'sep-late',settlementMonth:'2026-09',clientId:'c1',ownerType:'CLIENT',incomeType:'SERVICE_FEE',statusKey:'PENDING',unpaid:50,dueDate:'2026-09-20'},
  {id:'sep-early',settlementMonth:'2026-09',clientId:'c1',ownerType:'CLIENT',incomeType:'SERVICE_FEE',statusKey:'PARTIAL',unpaid:20,dueDate:'2026-09-05'},
  {id:'sep-nodue',settlementMonth:'2026-09',clientId:'c1',ownerType:'CLIENT',incomeType:'SERVICE_FEE',statusKey:'PENDING',unpaid:10},
  {id:'company',settlementMonth:'2026-09',clientId:null,ownerType:'COMPANY',incomeType:'OTHER',statusKey:'PAID',unpaid:0,dueDate:'2026-09-01'},
  {id:'default-fields',settlementMonth:'2026-08',clientId:'c1',unpaid:3,dueDate:'2026-08-01'},
  {id:'c2',settlementMonth:'2026-09',clientId:'c2',ownerType:'CLIENT',incomeType:'REBATE',statusKey:'OVERDUE',unpaid:9,dueDate:'2026-09-03'},
  {id:'out-period',settlementMonth:'2026-10',clientId:'c1',ownerType:'CLIENT',incomeType:'SERVICE_FEE',statusKey:'PENDING',unpaid:999,dueDate:'2026-10-01'},
];
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','company','c2','sep-early','sep-late','default-fields','aug-late'],'ALL filters + settlement sort/date sort');

subject.financeClientFilter='c1';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','sep-early','sep-late','default-fields','aug-late'],'client filter');
subject.financeClientFilter='ALL';subject.receivableOwnerFilter='CLIENT';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','c2','sep-early','sep-late','default-fields','aug-late'],'owner CLIENT filter incl default CLIENT');
subject.receivableOwnerFilter='COMPANY';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['company'],'owner COMPANY filter');
subject.receivableOwnerFilter='ALL';subject.receivableIncomeTypeFilter='SERVICE_FEE';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','sep-early','sep-late','default-fields','aug-late'],'income SERVICE_FEE filter incl default');
subject.receivableIncomeTypeFilter='REBATE';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['c2'],'income REBATE filter');
subject.receivableIncomeTypeFilter='ALL';subject.receivableStatusFilter='PARTIAL';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-early'],'status filter uses status-key authority');
subject.receivableStatusFilter='ALL';subject.receivableLedgerMode='OUTSTANDING';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','c2','sep-early','sep-late','default-fields','aug-late'],'OUTSTANDING excludes fully paid/zero-unpaid');
subject.receivableLedgerMode='ALL';subject.financeClientFilter='c1';subject.receivableOwnerFilter='CLIENT';subject.receivableIncomeTypeFilter='SERVICE_FEE';subject.receivableStatusFilter='PENDING';
jsonEq(subject.financeVisibleReceivables().map(r=>r.id),['sep-nodue','sep-late','default-fields','aug-late'],'all filters compose with AND semantics');

subject=makeSubject();
subject.clients=[{id:'c1',name:'Client One'},{id:2,name:'Client Two'}];
eq(subject.financeReceivableClientName({ownerType:'COMPANY',payerName:'  ACME Holdings  '}),'ACME Holdings','company payer trim');
eq(subject.financeReceivableClientName({ownerType:'COMPANY',payerName:'   '}),'公司收入 · 不关联客户','company blank payer fallback');
eq(subject.financeReceivableClientName({clientId:'c1'}),'Client One','client lookup');
eq(subject.financeReceivableClientName({clientId:'2'}),'Client Two','client lookup string-normalized id');
eq(subject.financeReceivableClientName({clientId:'missing'}),'客户已归档 / 删除','archived client fallback');

subject=makeSubject();
eq(subject.financeReceivableIncomeBreakdownText([]),'—','empty income breakdown');
eq(subject.financeReceivableIncomeBreakdownText(null),'—','null income breakdown');
eq(subject.financeReceivableIncomeBreakdownText([{incomeType:'SERVICE_FEE'},{incomeType:'REBATE'},{incomeType:'SERVICE_FEE'},{}, {incomeType:'OTHER'}]),'服务费 3 · 返点 1 · 其他收入 1','income breakdown counts + default service fee + insertion order');

subject=makeSubject();
subject.financeRows=['a','b','c','d','e','f','g'];subject.profitPageStart=2;subject.profitPageEnd=5;subject.profitPageSize=3;
jsonEq(subject.financeProfitPagedRows(),['c','d','e'],'profit page is pure final-row slice');
eq(subject.financeProfitTotalPages(),3,'profit total pages');
subject.financeRows=[];
eq(subject.financeProfitTotalPages(),1,'empty profit list exposes one page');
subject.financeRows=['a','b'];subject.profitPageSize=0;
eq(subject.financeProfitTotalPages(),2,'nonpositive page size floors denominator to one');

console.log('BUSINESS_FINANCE_VISIBLE_PROFIT_OK: receivable-filters+sort+client-name+income-breakdown+profit-pagination=executed');
