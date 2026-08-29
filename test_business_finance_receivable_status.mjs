import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: final runtime ${name} implementation not found`);
  const methodStart=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(methodStart);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: ${name} boundary parser drifted`);
  const nextStart=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,nextStart).replace(/,\s*$/,'').trim();
}

const names=[
  'financeReceivablePaid','financeReceivableUnpaid','financeReceivablePaidText','financeReceivableUnpaidText',
  'financeReceivableStatusKey','financeReceivableStatusText','financeReceivableStatusStyle','financeReceivableExpectedText',
  'financeReceivableMargin','financeReceivableMarginRate','financeReceivableTotals','financeSummaryReceivables',
  'financeReceivablePagedRows','financeReceivableTotalPages','financeInvoiceStatusText','financeCashReceivedGroups',
];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
function makeSubject(){
  const factory=`({
    financeReceivables:[], financeClientFilter:'ALL', financeActiveSnapshotScope:null,
    receivablePageStart:0, receivablePageEnd:10, receivablePageSize:10,
    financePeriodMonths(){return ['2026-08','2026-09'];},
    financeSettlementMonthMatch(month){return this.financePeriodMonths().includes(String(month||''));},
    localDateKey(){return '2026-08-29';}, spendGroupsText(groups){return JSON.stringify(groups);},
    ${names.map(name=>sources[name]).join(',\n    ')}
  })`;
  try{return vm.runInNewContext(factory,{Number,String,Object,Array,Set,Math,JSON},{timeout:1000});}
  catch(error){throw new Error(`BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: unable to execute final implementations: ${error.message}`);}
}

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_FINANCE_RECEIVABLE_STATUS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const near=(actual,expected,label)=>{if(Math.abs(Number(actual)-Number(expected))>1e-9)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};
const groupsEq=(actual,expected,label)=>{
  jsonEq(Object.keys(actual).sort(),Object.keys(expected).sort(),label+' currencies');
  for(const [currency,value] of Object.entries(expected))near(actual[currency],value,`${label} ${currency}`);
};

// Payment arithmetic: an explicit payments ledger is authoritative over legacy
// paidAmount, and unpaid balances are floored at zero.
let subject=makeSubject();
near(subject.financeReceivablePaid({payments:[{amount:30},{amount:'20.5'},{amount:null}],paidAmount:999}),50.5,'payments ledger sum');
near(subject.financeReceivablePaid({payments:[],paidAmount:999}),0,'empty payments ledger remains authoritative');
near(subject.financeReceivablePaid({paidAmount:'42.25'}),42.25,'legacy paidAmount fallback');
near(subject.financeReceivablePaid(null),0,'missing receivable paid amount');
near(subject.financeReceivableUnpaid({amount:100,payments:[{amount:30}]}),70,'unpaid amount');
near(subject.financeReceivableUnpaid({amount:100,payments:[{amount:120}]}),0,'overpayment does not create negative unpaid');

// Status semantics are amount-first, then strict overdue date, then partial/pending.
const paid={amount:100,payments:[{amount:100}],dueDate:'2026-08-01'};
const overpaid={amount:100,payments:[{amount:120}],dueDate:'2026-08-01'};
const overdue={amount:100,payments:[],dueDate:'2026-08-28'};
const partialOverdue={amount:100,payments:[{amount:25}],dueDate:'2026-08-28'};
const partialToday={amount:100,payments:[{amount:25}],dueDate:'2026-08-29'};
const pendingFuture={amount:100,payments:[],dueDate:'2026-08-30'};
for(const [row,key,text,style] of [
  [paid,'PAID','已收款','bg-emerald-50 text-emerald-700'],
  [overpaid,'PAID','已收款','bg-emerald-50 text-emerald-700'],
  [overdue,'OVERDUE','已逾期','bg-rose-50 text-rose-600'],
  [partialOverdue,'OVERDUE','部分逾期','bg-rose-50 text-rose-600'],
  [partialToday,'PARTIAL','部分收款','bg-blue-50 text-blue-700'],
  [pendingFuture,'PENDING','待收款','bg-amber-50 text-amber-700'],
]){
  eq(subject.financeReceivableStatusKey(row),key,`${text} status key`);
  eq(subject.financeReceivableStatusText(row),text,`${text} status text`);
  eq(subject.financeReceivableStatusStyle(row),style,`${text} status style`);
}

// Margin is receivable minus direct cost. Non-positive receivables intentionally do
// not display a percentage denominator.
near(subject.financeReceivableMargin({amount:200,directCost:50}),150,'receivable margin');
eq(subject.financeReceivableMarginRate({amount:200,directCost:50}),'75.00%','positive margin rate');
eq(subject.financeReceivableMarginRate({amount:100,directCost:125}),'-25.00%','negative margin rate');
eq(subject.financeReceivableMarginRate({amount:0,directCost:10}),'—','zero amount margin rate placeholder');
eq(subject.financeReceivableMarginRate({amount:-5,directCost:0}),'—','negative amount margin rate placeholder');

// Summary filtering is period-first and optionally client-scoped.
subject=makeSubject();
subject.financeReceivables=[
  {id:'a',clientId:'c1',settlementMonth:'2026-08'},
  {id:'b',clientId:'c2',settlementMonth:'2026-09'},
  {id:'c',clientId:'c1',settlementMonth:'2026-10'},
];
jsonEq(subject.financeSummaryReceivables().map(r=>r.id),['a','b'],'ALL summary period filter');
subject.financeClientFilter='c1';
jsonEq(subject.financeSummaryReceivables().map(r=>r.id),['a'],'client summary filter');

// Totals cap paid per row. When an active snapshot exists it is the expected-
// receivable authority; otherwise current summary rows provide expected totals.
subject=makeSubject();
const summaryRows=[
  {currency:'USD',amount:100,payments:[{amount:40}]},
  {currency:'USD',amount:50,payments:[{amount:60}]},
  {currency:'CNY',amount:80,payments:[{amount:20}]},
];
subject.financeSummaryReceivables=summaryRows;
subject.financeActiveSnapshotScope={receivableGroups:{USD:200,CNY:100,EUR:50}};
let totals=subject.financeReceivableTotals();
groupsEq(totals.expected,{USD:200,CNY:100,EUR:50},'snapshot expected totals');
groupsEq(totals.paid,{USD:90,CNY:20},'capped paid totals');
groupsEq(totals.unpaid,{USD:110,CNY:80,EUR:50},'snapshot unpaid totals');
subject.financeActiveSnapshotScope=null;
totals=subject.financeReceivableTotals();
groupsEq(totals.expected,{USD:150,CNY:80},'live expected totals fallback');
groupsEq(totals.paid,{USD:90,CNY:20},'live paid totals');
groupsEq(totals.unpaid,{USD:60,CNY:60},'live unpaid totals');
subject.financeActiveSnapshotScope={receivableGroups:{USD:50}};
totals=subject.financeReceivableTotals();
near(totals.unpaid.USD,0,'aggregate paid above snapshot expected floors unpaid at zero');

// Summary text helpers must render the corresponding expected/paid/unpaid group.
subject=makeSubject();
subject.financeReceivableTotals={expected:{USD:10},paid:{USD:4},unpaid:{USD:6}};
const rendered=[];
subject.spendGroupsText=groups=>{rendered.push(groups);return `G:${JSON.stringify(groups)}`;};
eq(subject.financeReceivableExpectedText(),'G:{"USD":10}','expected text helper');
eq(subject.financeReceivablePaidText(),'G:{"USD":4}','paid text helper');
eq(subject.financeReceivableUnpaidText(),'G:{"USD":6}','unpaid text helper');
eq(rendered[0],subject.financeReceivableTotals.expected,'expected helper passes expected group');
eq(rendered[1],subject.financeReceivableTotals.paid,'paid helper passes paid group');
eq(rendered[2],subject.financeReceivableTotals.unpaid,'unpaid helper passes unpaid group');

// Pagination is a pure slice over the visible authority and always exposes at least
// one page for an empty result set.
subject=makeSubject();
subject.financeVisibleReceivables=[1,2,3,4,5,6,7];
subject.receivablePageStart=2;subject.receivablePageEnd=5;subject.receivablePageSize=3;
jsonEq(subject.financeReceivablePagedRows(),[3,4,5],'receivable page slice');
eq(subject.financeReceivableTotalPages(),3,'receivable page count');
subject.financeVisibleReceivables=[];
eq(subject.financeReceivableTotalPages(),1,'empty receivable list still has one page');

// Invoice status labels keep the known 3-state vocabulary and fail to the pending
// label for unknown/blank historical values.
subject=makeSubject();
eq(subject.financeInvoiceStatusText('NONE'),'无需开票','invoice none label');
eq(subject.financeInvoiceStatusText('PENDING'),'待开票','invoice pending label');
eq(subject.financeInvoiceStatusText('ISSUED'),'已开票','invoice issued label');
eq(subject.financeInvoiceStatusText('UNKNOWN'),'待开票','invoice unknown fallback');
eq(subject.financeInvoiceStatusText(null),'待开票','invoice blank fallback');

// Cash received is payment-date-period based (not settlement-month based), uses the
// receivable currency/default USD, and respects the optional client filter.
subject=makeSubject();
subject.financePeriodMonths=()=>['2026-08','2026-09'];
subject.financeReceivables=[
  {clientId:'c1',currency:'USD',settlementMonth:'2026-07',payments:[{date:'2026-08-01',amount:10},{date:'2026-09-02',amount:'5'},{date:'2026-10-01',amount:99}]},
  {clientId:'c1',currency:'CNY',payments:[{date:'2026-08-03',amount:20}]},
  {clientId:'c2',currency:'USD',payments:[{date:'2026-08-04',amount:50}]},
  {clientId:'c1',payments:[{date:'2026-09-05',amount:3}]},
  {clientId:'c1',currency:'USD',paidAmount:777},
];
subject.financeClientFilter='ALL';
groupsEq(subject.financeCashReceivedGroups(),{USD:68,CNY:20},'ALL cash received by payment month');
subject.financeClientFilter='c1';
groupsEq(subject.financeCashReceivedGroups(),{USD:18,CNY:20},'client cash received by payment month');

console.log('BUSINESS_FINANCE_RECEIVABLE_STATUS_OK: payment-ledger+four-state-status+margin+totals+summary+pagination+invoice+cash-received=executed');
