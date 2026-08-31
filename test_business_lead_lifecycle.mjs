import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_LEAD_LIFECYCLE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_LEAD_LIFECYCLE_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_LIFECYCLE_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_LEAD_LIFECYCLE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const methodNames=[
  'defaultLeadForm','saveLead','convertLeadToClient','openConvertedLeadClient',
  'leadStats','filteredLeads','saveClient','ensureClientFirstReceivable'
];
const methodSource=methodNames.map(extractMethod).join(',\n');
let methods;
try{methods=vm.runInNewContext(`({${methodSource}})`,Object.create(null),{timeout:1000})}
catch(error){throw new Error(`BUSINESS_LEAD_LIFECYCLE_FAILED: unable to execute final runtime methods: ${error.message}`)}
for(const name of methodNames)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_LEAD_LIFECYCLE_FAILED: ${name} is not executable`);

const fail=message=>{throw new Error('BUSINESS_LEAD_LIFECYCLE_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(`${label}; expected=${e}; actual=${a}`)};
const makeSubject=extra=>Object.assign({},methods,extra||{});

// Default lead form is the lifecycle schema authority used for every new lead.
const defaultLead=methods.defaultLeadForm();
eq(defaultLead.stage,'NEW','default lead stage');
eq(defaultLead.source,'网站询盘','default lead source');
eq(defaultLead.platformInterest,'FB+TK','default lead platform interest');
eq(defaultLead.budgetCurrency,'USD','default budget currency');
eq(defaultLead.quoteCurrency,'USD','default quote currency');
eq(defaultLead.convertedClientId,null,'default converted client id');
eq(defaultLead.convertedAt,'','default converted timestamp');

// New lead save: normalize money, assign stable lead identity/date, persist exactly once.
{
  let persisted=0,audited=0,notified='';
  const s=makeSubject({
    leadForm:{...defaultLead,company:'Acme Prospect',budgetCurrency:'CNY',quoteCurrency:'',expectedBudget:'1200.50',adQuote:'',nextFollowUp:'2026-09-03'},
    leads:[],showLeadModal:true,leadPoolFilter:'',leadQuickFilter:'',
    accountUid:kind=>kind==='lead'?'lead-001':'unexpected',localDateKey:()=> '2026-08-30',
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:msg=>{notified=msg},leadStageText:value=>value,
  });
  s.saveLead();
  eq(s.leads.length,1,'new lead inserted exactly once');
  eq(s.leads[0].id,'lead-001','new lead id');
  eq(s.leads[0].createdAt,'2026-08-30','new lead created date');
  eq(s.leads[0].expectedBudget,1200.5,'expected budget numeric normalization');
  eq(s.leads[0].adQuote,0,'empty quote numeric normalization');
  eq(s.leads[0].quoteCurrency,'CNY','quote currency falls back to budget currency');
  eq(persisted,1,'new lead persistence count');
  eq(audited,1,'new lead audit count');
  eq(s.showLeadModal,false,'new lead closes modal');
  eq(s.leadPoolFilter,'ACTIVE','new lead returns to active pool');
  if(!notified.includes('已保存'))fail('new lead success notification missing');
}

// Terminal/converted lead states clear follow-up and converted identity forces WON.
{
  const lead={...defaultLead,id:'lead-002',company:'Won Co',stage:'QUALIFIED',nextFollowUp:'2026-09-01',convertedClientId:'client-9'};
  const s=makeSubject({leadForm:{...lead},leads:[lead],persist:()=>{},logAudit:()=>{},notify:()=>{},leadStageText:v=>v,showLeadModal:true});
  s.saveLead();
  eq(s.leads[0].stage,'WON','converted lead must be WON');
  eq(s.leads[0].nextFollowUp,'','converted/WON lead clears follow-up');
}
{
  const lead={...defaultLead,id:'lead-003',company:'Lost Co',stage:'LOST',nextFollowUp:'2026-09-01'};
  const s=makeSubject({leadForm:{...lead},leads:[lead],persist:()=>{},logAudit:()=>{},notify:()=>{},leadStageText:v=>v,showLeadModal:true});
  s.saveLead();
  eq(s.leads[0].nextFollowUp,'','LOST lead clears follow-up');
  eq(s.leadPoolFilter,'LOST','LOST lead moves to lost pool');
}

// Conversion preparation preserves the lead linkage and quote precedence.
{
  let destination='';
  const s=makeSubject({
    defaultForm:()=>({fbAccounts:[{id:'fb1'}],tkAccounts:[{id:'tk1'}],billingMode:'FULL_MONTH'}),
    localDateKey:()=> '2026-08-30',addDays:(date,days)=>date==='2026-08-30'&&days===30?'2026-09-29':'bad',
    notify:()=>{},navigateTo:page=>{destination=page},showLeadModal:true,
  });
  s.convertLeadToClient({id:'lead-q',company:'Quoted Co',platformInterest:'FB',budgetCurrency:'USD',expectedBudget:999,quoteCurrency:'CNY',adQuote:150});
  eq(s.form.sourceLeadId,'lead-q','conversion preserves source lead id');
  eq(s.form.name,'Quoted Co','conversion copies company name');
  eq(s.form.platform,'FB','conversion copies platform');
  eq(s.form.currency,'CNY','positive quote chooses quote currency');
  eq(s.form.monthlyFee,150,'positive quote takes precedence over expected budget');
  eq(s.form.startDate,'2026-08-30','conversion start date');
  eq(s.form.endDate,'2026-09-29','conversion end date +30 days');
  eq(s.form.tkAccounts.length,0,'FB-only conversion removes TikTok accounts');
  eq(s.form.fbAccounts.length,1,'FB-only conversion preserves Facebook accounts');
  eq(destination,'client-form','conversion navigates to client form');
}
{
  const s=makeSubject({defaultForm:()=>({fbAccounts:[],tkAccounts:[]}),localDateKey:()=> '2026-08-30',addDays:()=> '2026-09-29',notify:()=>{},navigateTo:()=>{}});
  s.convertLeadToClient({id:'lead-budget',company:'Budget Co',platformInterest:'TK',budgetCurrency:'USD',expectedBudget:888,quoteCurrency:'CNY',adQuote:0});
  eq(s.form.currency,'USD','zero quote falls back to budget currency');
  eq(s.form.monthlyFee,888,'zero quote falls back to expected budget');
  eq(s.form.fbAccounts.length,0,'TK-only conversion removes Facebook accounts');
}
{
  let opened=0;
  const s=makeSubject({openConvertedLeadClient:()=>{opened+=1},defaultForm:()=>fail('already converted lead must not prepare duplicate client form')});
  s.convertLeadToClient({id:'lead-done',convertedClientId:'client-existing'});
  eq(opened,1,'already converted lead opens existing client');
}

// Missing linked client recovers the lead relationship instead of navigating stale state.
{
  let persisted=0,notified='';
  const lead={id:'lead-missing',convertedClientId:'gone',convertedAt:'2026-08-01T00:00:00.000Z',stage:'WON'};
  const s=makeSubject({clients:[],persist:()=>{persisted+=1},notify:msg=>{notified=msg},navigateTo:()=>fail('missing linked client must not navigate')});
  s.openConvertedLeadClient(lead);
  eq(lead.convertedClientId,null,'missing linked client clears converted id');
  eq(lead.convertedAt,'','missing linked client clears converted timestamp');
  eq(persisted,1,'missing linked client repair persists');
  if(!notified.includes('已不存在'))fail('missing linked client recovery notification missing');
}

// Lead statistics and filtering: converted/terminal leads leave active pool; due is inclusive of today.
{
  const leads=[
    {id:'a',company:'Today',stage:'NEW',nextFollowUp:'2026-08-30',createdAt:'2026-08-01'},
    {id:'b',company:'Overdue',stage:'QUALIFIED',nextFollowUp:'2026-08-29',createdAt:'2026-08-02'},
    {id:'c',company:'Future',stage:'PROPOSAL',nextFollowUp:'2026-09-01',createdAt:'2026-08-03'},
    {id:'g',company:'No Date',stage:'NEW',nextFollowUp:'',createdAt:'2026-08-04'},
    {id:'d',company:'Won Stage',stage:'WON',nextFollowUp:'',createdAt:'2026-08-05'},
    {id:'e',company:'Lost',stage:'LOST',nextFollowUp:'',createdAt:'2026-08-06'},
    {id:'f',company:'Converted',stage:'NEW',convertedClientId:'client-f',convertedAt:'2026-08-10T00:00:00.000Z',createdAt:'2026-08-07'},
  ];
  const s=makeSubject({leads,localDateKey:()=> '2026-08-30',leadSearch:'',leadPoolFilter:'ACTIVE',leadQuickFilter:'ALL'});
  jsonEq(s.leadStats(),{total:4,due:2,qualified:2,won:2},'lead statistics');
  jsonEq(s.filteredLeads().map(x=>x.id),['b','a','c','g'],'active lead due-date ordering');
  s.leadQuickFilter='DUE';jsonEq(s.filteredLeads().map(x=>x.id),['b','a'],'due quick filter');
  s.leadQuickFilter='HIGH';jsonEq(s.filteredLeads().map(x=>x.id),['b','c'],'high-intent quick filter');
  s.leadPoolFilter='WON';s.leadQuickFilter='ALL';jsonEq(new Set(s.filteredLeads().map(x=>x.id)),new Set(['d','f']),'WON pool includes stage-won and converted leads');
  s.leadPoolFilter='LOST';jsonEq(s.filteredLeads().map(x=>x.id),['e'],'LOST pool excludes converted leads');
}

// First receivable policy: manual billing creates nothing; automatic billing uses contract start month.
{
  let calls=[];
  const s=makeSubject({localDateKey:()=> '2026-08-30',createReceivableForClientMonth:(client,month,opts)=>{calls.push({client,month,opts});return 1}});
  eq(s.ensureClientFirstReceivable({id:'m',billingMode:'MANUAL',startDate:'2026-02-15'}),0,'manual billing first receivable');
  eq(calls.length,0,'manual billing must not create receivable');
  eq(s.ensureClientFirstReceivable({id:'a',billingMode:'FULL_MONTH',startDate:'2026-02-15'}),1,'automatic billing first receivable return');
  eq(calls.length,1,'automatic billing creates exactly one first receivable');
  eq(calls[0].month,'2026-02','automatic billing uses start month');
  eq(calls[0].opts.allowFuture,true,'first receivable explicitly allows future start month');
}

// Saving a new formal client from a lead must atomically link the lead and start billing hooks.
{
  let persisted=0,audited=0,navigated='',firstBills=0,catchups=0,assetCosts=0;
  const lead={id:'lead-link',company:'Lead Link',stage:'QUALIFIED',nextFollowUp:'2026-09-02',convertedClientId:null,convertedAt:''};
  const s=makeSubject({
    form:{id:null,sourceLeadId:'lead-link',name:'Lead Link',billingMode:'FULL_MONTH',monthlyFee:500,currency:'USD'},
    clients:[],leads:[lead],
    defaultForm:()=>({billingMode:'FULL_MONTH',monthlyFee:0,currency:'USD'}),
    cleanPlatformAccounts:()=>{},cleanNetworkEnvironments:()=>{},normalizeClient:value=>({...value}),
    ensureClientFirstReceivable:()=>{firstBills+=1;return 1},
    ensureAutomaticReceivables:()=>{catchups+=1;return 2},
    ensureAutomaticAssetCosts:()=>{assetCosts+=1;return 3},
    localDateKey:()=> '2026-08-30',persist:()=>{persisted+=1},logAudit:()=>{audited+=1},
    formatMoney:(value,currency)=>`${currency}:${value}`,notify:()=>{},navigateTo:page=>{navigated=page},formDirty:true,
  });
  s.saveClient();
  eq(s.clients.length,1,'lead conversion creates exactly one formal client');
  const client=s.clients[0];
  eq(client.sourceLeadId,'lead-link','formal client retains source lead id');
  eq(s.selectedClientId,client.id,'new client selected in client module');
  eq(s.selectedAssetsClientId,client.id,'new client selected in assets module');
  eq(s.selectedSopClientId,client.id,'new client selected in SOP module');
  eq(s.selectedAnalyticsClientId,client.id,'new client selected in analytics module');
  eq(s.selectedAdsClientId,client.id,'new client selected in ads module');
  eq(firstBills,1,'new client first-receivable hook count');
  eq(catchups,1,'new client catch-up receivable hook count');
  eq(assetCosts,1,'new client asset-cost hook count');
  eq(lead.stage,'WON','source lead marked WON after client save');
  eq(String(lead.convertedClientId),String(client.id),'source lead linked to created client');
  if(!lead.convertedAt||!/^\d{4}-\d{2}-\d{2}T/.test(lead.convertedAt))fail('source lead convertedAt not recorded');
  eq(lead.nextFollowUp,'','source lead follow-up cleared after conversion');
  eq(persisted,1,'new formal client persistence count');
  eq(audited,1,'new formal client audit count');
  eq(navigated,'client-detail','new formal client navigates to detail');
  eq(s.formDirty,false,'new formal client clears dirty flag');
}

// Stale edit IDs must fail closed. A record deleted in another tab/session must not
// produce a fake success, phantom billing, or audit trail against an absent entity.
{
  let persisted=0,audited=0,notified='';
  const s=makeSubject({
    leadForm:{...defaultLead,id:'lead-gone',company:'Stale Lead',stage:'QUALIFIED'},leads:[],showLeadModal:true,
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:msg=>{notified=msg},leadStageText:v=>v,
  });
  s.saveLead();
  eq(persisted,0,'stale lead edit must not persist fake success');
  eq(audited,0,'stale lead edit must not write audit success');
  eq(s.showLeadModal,true,'stale lead edit keeps form open to preserve edits');
  if(!/不存在|刷新/.test(notified))fail('stale lead edit must notify that record no longer exists');
}
{
  let persisted=0,audited=0,billing=0,navigated='',notified='';
  const s=makeSubject({
    form:{id:'client-gone',name:'Stale Client',billingMode:'FULL_MONTH',monthlyFee:99,currency:'USD'},clients:[],
    cleanPlatformAccounts:()=>{},cleanNetworkEnvironments:()=>{},normalizeClient:value=>value,
    ensureAutomaticReceivables:()=>{billing+=1;return 1},ensureAutomaticAssetCosts:()=>{billing+=1;return 1},
    localDateKey:()=> '2026-08-30',persist:()=>{persisted+=1},logAudit:()=>{audited+=1},auditDiff:()=>'',
    notify:msg=>{notified=msg},navigateTo:page=>{navigated=page},formDirty:true,
  });
  s.saveClient();
  eq(persisted,0,'stale client edit must not persist fake success');
  eq(audited,0,'stale client edit must not write audit success');
  eq(billing,0,'stale client edit must not create receivable/cost side effects');
  eq(navigated,'','stale client edit must not navigate away');
  eq(s.formDirty,true,'stale client edit keeps unsaved form state');
  if(!/不存在|刷新/.test(notified))fail('stale client edit must notify that record no longer exists');
}

console.log('BUSINESS_LEAD_LIFECYCLE_OK: default+save+terminal-state+filter+stats+convert+client-link+first-receivable+missing-link-repair+stale-edit-fail-closed=executed');
