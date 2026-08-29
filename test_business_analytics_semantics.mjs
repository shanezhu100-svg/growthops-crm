import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_ANALYTICS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_ANALYTICS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_ANALYTICS_FAILED: ${name} not found in final app`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_ANALYTICS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  'analyticsMetricsForAccount',
  'aggregateAccountsMetrics',
  'analyticsAllFbAccounts',
  'analyticsAllTkAccounts',
  'analyticsAllClientRows',
  'syncAnalyticsAccountSelection',
  'selectedAnalyticsFbMetrics',
  'selectedAnalyticsTkMetrics',
];
const methods={};
for(const name of names){
  const obj=vm.runInNewContext(`({${extractMethod(name)}})`,{Number,String,Object,Array,Math,Intl,console},{timeout:1000});
  methods[name]=obj[name];
}
const call=(name,subject,...args)=>methods[name].call(subject,...args);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_ANALYTICS_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};

// Account-level analytics must prefer actual adDataRecords and translate the
// canonical account summary into the Analytics card contract. This intentionally
// stubs only the already-tested summary helper, not the Analytics mapping itself.
{
  const account={id:'fb1',adDataRecords:[{date:'2026-08-01'}]};
  const subject={
    accountDataSummary:()=>({leads:7,cplText:'USD 2.00',impressions:1234,cpmText:'USD 5.00',ctrText:'1.25%',cpcText:'USD 0.40',cvrText:'20.00%',cpaText:'USD 2.00',roasText:'3.50'}),
    selectedAnalyticsClient:null,
  };
  const out=call('analyticsMetricsForAccount',subject,account,'FB');
  eq(out.leads,7,'record-backed account leads');
  eq(String(out.impressions).replace(/\D/g,''),'1234','record-backed impressions formatting');
  jsonEq([out.cpl,out.cpm,out.ctr,out.cpc,out.cvr,out.cpa,out.roas],['USD 2.00','USD 5.00','1.25%','USD 0.40','20.00%','USD 2.00','3.50'],'record-backed metric mapping');
}

// Legacy platform fallback is permitted only when that client has exactly one
// account for the platform. Missing optional cost metrics normalize to empty text.
{
  const account={id:'fb1',adDataRecords:[]};
  const subject={selectedAnalyticsClient:{fbAccounts:[account],fbData:{leads:4,impressions:'100',ctr:'2%',roas:'1.80'}}};
  const out=call('analyticsMetricsForAccount',subject,account,'FB');
  eq(out.leads,4,'single-account FB fallback retained');
  jsonEq([out.cpm,out.cpc,out.cvr,out.cpa],['','','',''],'fallback missing optional metrics normalize to blank');
  subject.selectedAnalyticsClient.fbAccounts.push({id:'fb2'});
  eq(call('analyticsMetricsForAccount',subject,account,'FB'),null,'multi-account client must not reuse ambiguous legacy FB fallback');
  eq(call('analyticsMetricsForAccount',subject,null,'FB'),null,'null account returns no analytics');
}

// Aggregate analytics performs cross-account totals but only computes monetary
// efficiency metrics when spend is in one currency. CTR/CVR remain valid ratios.
const records=[
  {impressions:1000,clicks:100,leads:20,conversions:10,revenue:60,currency:'USD'},
  {impressions:500,clicks:25,leads:5,conversions:5,revenue:15,currency:'USD'},
];
const accounts=[{id:'a1',adDataRecords:[records[0]]},{id:'a2',adDataRecords:[records[1]]}];
{
  const subject={
    spendGroups:()=>({USD:30}),
    spendGroupsText:()=> 'USD 30.00',
    formatMoney:(value,currency)=>`${currency} ${Number(value).toFixed(2)}`,
  };
  const out=call('aggregateAccountsMetrics',subject,accounts);
  jsonEq([out.records,out.impressions,out.clicks,out.leads,out.conversions],[2,1500,125,25,15],'aggregate count totals');
  jsonEq([out.cpmText,out.ctrText,out.cpcText,out.cvrText,out.cpaText,out.roasText],['USD 20.00','8.33%','USD 0.24','12.00%','USD 2.00','2.50'],'single-currency aggregate efficiency metrics');
  eq(out.spendText,'USD 30.00','aggregate spend text delegates canonical formatter');
}
{
  const subject={
    spendGroups:()=>({USD:20,EUR:10}),
    spendGroupsText:()=> 'USD 20.00 + EUR 10.00',
    formatMoney:(value,currency)=>`${currency} ${Number(value).toFixed(2)}`,
  };
  const mixed=[
    {id:'u',adDataRecords:[{impressions:100,clicks:10,leads:2,conversions:1,revenue:30,currency:'USD'}]},
    {id:'e',adDataRecords:[{impressions:100,clicks:10,leads:2,conversions:1,revenue:20,currency:'EUR'}]},
  ];
  const out=call('aggregateAccountsMetrics',subject,mixed);
  jsonEq([out.cpmText,out.cpcText,out.cpaText,out.roasText],['—','—','—','—'],'mixed currencies deny combined monetary efficiency metrics');
  jsonEq([out.ctrText,out.cvrText],['10.00%','10.00%'],'mixed currencies preserve non-monetary ratios');
  eq(out.spendText,'USD 20.00 + EUR 10.00','mixed currency spend remains explicit');
}

// All-client account inventories flatten only active clients, while the client row
// view counts FB/TK records and sorts by record coverage before client name.
{
  const activeClients=[
    {id:'alpha',name:'Alpha',fbAccounts:[{id:'af',adDataRecords:[{},{}]}],tkAccounts:[]},
    {id:'beta',name:'Beta',fbAccounts:[],tkAccounts:[{id:'bt',adDataRecords:[{},{},{}]}]},
    {id:'gamma',name:'Gamma',fbAccounts:[{id:'gf',adDataRecords:[{}]}],tkAccounts:[{id:'gt',adDataRecords:[]}]},
  ];
  jsonEq(call('analyticsAllFbAccounts',{activeClients}).map(a=>a.id),['af','gf'],'all-client FB account flattening');
  jsonEq(call('analyticsAllTkAccounts',{activeClients}).map(a=>a.id),['bt','gt'],'all-client TK account flattening');
  const subject={activeClients,clientSpendText:c=>`spend:${c.id}`,clientRechargeText:c=>`recharge:${c.id}`};
  const rows=call('analyticsAllClientRows',subject);
  jsonEq(rows.map(r=>r.client.id),['beta','alpha','gamma'],'all-client analytics rows sort by record coverage');
  jsonEq([rows[0].fbAccounts,rows[0].tkAccounts,rows[0].records],[0,1,3],'all-client row FB/TK/record counts');
  jsonEq([rows[1].spendText,rows[1].rechargeText],['spend:alpha','recharge:alpha'],'all-client row spend/recharge delegates canonical client formatters');
}

// Selection synchronization repairs stale platform account IDs to the first valid
// account, preserves valid IDs using string-equivalent comparison, and clears both
// selections when the aggregate/no-client context is active.
{
  const subject={selectedAnalyticsClient:null,selectedAnalyticsFbAccountId:'stale',selectedAnalyticsTkAccountId:'stale'};
  call('syncAnalyticsAccountSelection',subject);
  jsonEq([subject.selectedAnalyticsFbAccountId,subject.selectedAnalyticsTkAccountId],[null,null],'no selected client clears platform account selections');
}
{
  const client={fbAccounts:[{id:1},{id:2}],tkAccounts:[{id:'t1'}]};
  const subject={selectedAnalyticsClient:client,selectedAnalyticsFbAccountId:'2',selectedAnalyticsTkAccountId:'stale'};
  call('syncAnalyticsAccountSelection',subject);
  jsonEq([subject.selectedAnalyticsFbAccountId,subject.selectedAnalyticsTkAccountId],['2','t1'],'valid string-equivalent FB selection preserved and stale TK repaired');
  subject.selectedAnalyticsFbAccountId='missing';
  subject.selectedAnalyticsTkAccountId='t1';
  call('syncAnalyticsAccountSelection',subject);
  jsonEq([subject.selectedAnalyticsFbAccountId,subject.selectedAnalyticsTkAccountId],[1,'t1'],'stale FB selection repairs to first account');
}
{
  const subject={selectedAnalyticsClient:{fbAccounts:[],tkAccounts:[]},selectedAnalyticsFbAccountId:'x',selectedAnalyticsTkAccountId:'y'};
  call('syncAnalyticsAccountSelection',subject);
  jsonEq([subject.selectedAnalyticsFbAccountId,subject.selectedAnalyticsTkAccountId],[null,null],'empty platform account lists clear stale selections');
}

// Selected-platform computed wrappers must route through the Analytics account metric
// function with the correct account and platform discriminator.
{
  const calls=[];
  const subject={
    selectedAnalyticsFbAccount:{id:'f'},selectedAnalyticsTkAccount:{id:'t'},
    analyticsMetricsForAccount:(account,platform)=>{calls.push([account.id,platform]);return `${platform}:${account.id}`;},
  };
  eq(call('selectedAnalyticsFbMetrics',subject),'FB:f','selected FB metric wrapper');
  eq(call('selectedAnalyticsTkMetrics',subject),'TK:t','selected TK metric wrapper');
  jsonEq(calls,[['f','FB'],['t','TK']],'selected metric wrappers preserve platform routing');
}

console.log('BUSINESS_ANALYTICS_OK: record+legacy-account-metrics; aggregate=same-currency+mixed-currency; all-client=fb+tk+records+sort; selection=clear+preserve+repair; wrappers=FB+TK');
