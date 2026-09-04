import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_COST_MUTATIONS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_COST_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_COST_MUTATIONS_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_COST_MUTATIONS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['saveFinanceCost','deleteFinanceCost','syncFinancePeriodAutoCosts','ensureAutomaticAssetCosts'];
let methods;
try{methods=vm.runInNewContext(`({${names.map(extractMethod).join(',\n')}})`,{Number,String,Object,Array,Math,Set,JSON},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_FINANCE_COST_MUTATIONS_FAILED: unable to execute final methods: ${error.message}`)}
for(const name of names)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_FINANCE_COST_MUTATIONS_FAILED: ${name} is not executable`);
const subject=extra=>Object.assign({},methods,extra||{});
const fail=message=>{throw new Error('BUSINESS_FINANCE_COST_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const ok=(value,label)=>{if(!value)fail(label)};

function manualCostBase(overrides={}){
  return subject({
    costForm:{id:'',date:'2026-09-01',category:'OTHER',scope:'COMPANY',clientId:'',currency:'USD',amount:'10'},
    financeCosts:[],showCostModal:true,
    normalizeFinanceCost:value=>({...value}),
    assertMonthUnlocked:()=>true,
    accountUid:()=> 'cost-new',
    financeCostCategoryText:value=>String(value),
    financeCostScopeText:value=>String(value.scope||''),
    formatMoney:(value,currency)=>`${currency}:${value}`,
    persist:()=>{},persistFinanceCostBarrier:async()=>{},logAudit:()=>{},notify:()=>{},
    ...overrides,
  });
}

// Manual cost input is finite/nonnegative before month-lock/mutation/persist.
for(const [raw,label] of [['-1','negative'],['abc','nan'],['Infinity','infinity']]){
  let lockChecks=0,persisted=0,audited=0,barrierCalls=0; const notices=[];
  const s=manualCostBase({
    costForm:{id:'',date:'2026-09-01',category:'OTHER',scope:'COMPANY',currency:'USD',amount:raw},
    assertMonthUnlocked:()=>{lockChecks+=1;return true},persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},logAudit:()=>{audited+=1},notify:m=>notices.push(m),
  });
  s.saveFinanceCost();
  eq(lockChecks,0,`${label} manual cost stops before month-lock lookup`);
  eq(s.financeCosts.length,0,`${label} manual cost must not mutate costs`);
  eq(persisted,0,`${label} manual cost must not persist`);
  eq(barrierCalls,0,`${label} manual cost must not cross durable barrier`);
  eq(audited,0,`${label} manual cost must not audit`);
  ok(notices.some(m=>m.includes('有效成本')),`${label} manual cost validation notice missing`);
}
{
  let lockChecks=0,persisted=0,barrierCalls=0;
  const s=manualCostBase({
    costForm:{date:'2026-09-01',category:'OTHER',scope:'CLIENT',clientId:'',currency:'USD',amount:'10'},
    assertMonthUnlocked:()=>{lockChecks+=1;return true},persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},
  });
  const notices=[];s.notify=m=>notices.push(m);s.saveFinanceCost();
  eq(lockChecks,0,'client cost missing client stops before month-lock lookup');
  eq(persisted,0,'client cost missing client must not persist');
  eq(barrierCalls,0,'client cost missing client must not cross durable barrier');
  ok(notices.some(m=>m.includes('必须选择客户')),'client cost missing-client notice');
}
{
  let persisted=0,audited=0,barrierCalls=0;
  const s=manualCostBase({assertMonthUnlocked:()=>false,persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},logAudit:()=>{audited+=1}});
  s.saveFinanceCost();
  eq(s.financeCosts.length,0,'locked manual cost must not mutate');
  eq(persisted,0,'locked manual cost must not persist');
  eq(barrierCalls,0,'locked manual cost must not cross durable barrier');
  eq(audited,0,'locked manual cost must not audit');
}
{
  let persisted=0,barrierCalls=0;const audits=[];const notices=[];
  const s=manualCostBase({persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},logAudit:(a,t)=>audits.push([a,t]),notify:m=>notices.push(m)});
  await s.saveFinanceCost();
  eq(s.financeCosts.length,1,'valid new manual cost inserts once');
  eq(s.financeCosts[0].id,'cost-new','valid new manual cost allocates id');
  eq(s.financeCosts[0].amount,10,'valid new manual cost normalizes numeric amount');
  eq(s.showCostModal,false,'valid manual cost closes modal after ACK');
  eq(persisted,0,'valid new manual cost uses durable barrier instead of debounced persist');
  eq(barrierCalls,1,'valid new manual cost crosses durable barrier once');
  eq(audits.length,1,'valid new manual cost audits once');
  eq(audits[0][0],'新增成本','new manual cost audit action');
  ok(notices.some(m=>m.includes('成本已保存')),'valid manual cost success notice');
}
{
  const existing={id:'cost-1',date:'2026-08-01',category:'OLD',scope:'COMPANY',currency:'USD',amount:1};
  let persisted=0,barrierCalls=0;const audits=[];
  const s=manualCostBase({
    financeCosts:[existing],
    costForm:{id:'cost-1',date:'2026-09-02',category:'NEW',scope:'COMPANY',clientId:'',currency:'CNY',amount:'22'},
    persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},logAudit:(a,t)=>audits.push([a,t]),
  });
  await s.saveFinanceCost();
  eq(s.financeCosts.length,1,'manual cost edit must not duplicate');
  eq(s.financeCosts[0].id,'cost-1','manual cost edit preserves id');
  eq(s.financeCosts[0].amount,22,'manual cost edit replaces amount');
  eq(s.financeCosts[0].currency,'CNY','manual cost edit replaces currency');
  eq(persisted,0,'manual cost edit uses durable barrier instead of debounced persist');
  eq(barrierCalls,1,'manual cost edit crosses durable barrier once');
  eq(audits[0][0],'修改成本','manual cost edit audit action');
}

// Automatic costs cannot be manually deleted, while normal deletions remain month-
// lock and confirmation gated with mutation/persist/audit only after confirmation.
for(const [sourceType,copy] of [
  ['OPENING_DEAL','自动开户成本不能单独删除'],
  ['RECEIVABLE_ITEM','收入项目联动成本不能单独删除'],
  ['IP_ENV_MONTH','自动 IP / 网络成本不能单独删除'],
]){
  let locks=0,confirms=0,persisted=0,barrierCalls=0;const notices=[];
  const cost={id:'auto',autoGenerated:true,sourceType,date:'2026-09-01',category:'IP',currency:'USD',amount:10};
  const s=manualCostBase({financeCosts:[cost],assertMonthUnlocked:()=>{locks+=1;return true},askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},notify:m=>notices.push(m)});
  s.deleteFinanceCost(cost);
  eq(locks,0,`${sourceType} delete stops before month-lock`);eq(confirms,0,`${sourceType} delete does not confirm`);eq(persisted,0,`${sourceType} delete does not persist`);eq(barrierCalls,0,`${sourceType} delete does not cross durable barrier`);
  eq(s.financeCosts.length,1,`${sourceType} delete preserves automatic row`);ok(notices.some(m=>m.includes(copy)),`${sourceType} delete notice`);
}
{
  const cost={id:'manual',date:'2026-09-01',category:'OTHER',currency:'USD',amount:10};
  let confirms=0,persisted=0,barrierCalls=0;
  const s=manualCostBase({financeCosts:[cost],assertMonthUnlocked:()=>false,askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1}});
  s.deleteFinanceCost(cost);eq(confirms,0,'locked manual delete must not confirm');eq(persisted,0,'locked manual delete must not persist');eq(barrierCalls,0,'locked manual delete must not cross durable barrier');eq(s.financeCosts.length,1,'locked manual delete preserves row');
}
{
  const target={id:'manual',date:'2026-09-01',category:'OTHER',currency:'USD',amount:10};const keep={id:'keep'};
  let action=null,persisted=0,barrierCalls=0;const audits=[];
  const s=manualCostBase({financeCosts:[target,keep],askConfirm:(cfg,cb)=>{eq(cfg.title,'删除成本记录','manual delete confirmation title');action=cb},persist:()=>{persisted+=1},persistFinanceCostBarrier:async()=>{barrierCalls+=1},logAudit:(a,t)=>audits.push([a,t])});
  s.deleteFinanceCost(target);eq(s.financeCosts.length,2,'manual delete must not mutate before confirmation');eq(persisted,0,'manual delete must not persist before confirmation');eq(barrierCalls,0,'manual delete must not cross durable barrier before confirmation');ok(typeof action==='function','manual delete confirmation callback');
  await action();eq(s.financeCosts.length,1,'confirmed manual delete removes one row');eq(s.financeCosts[0],keep,'confirmed manual delete preserves unrelated row');eq(persisted,0,'confirmed manual delete uses durable barrier instead of debounced persist');eq(barrierCalls,1,'confirmed manual delete crosses durable barrier once');eq(audits[0][0],'删除成本','confirmed manual delete audit action');
}

function autoBase(overrides={}){
  return subject({
    clients:[],financeCosts:[],
    localDateKey:()=> '2026-09-01',isMonthLocked:()=>false,
    clientContractOverlapsMonth:()=>true,
    accountUid:()=> 'cost-ip-new',monthDueDate:(month,day)=>`${month}-${String(day).padStart(2,'0')}`,
    normalizeFinanceCost:value=>({...value}),persist:()=>{},notify:()=>{},
    ...overrides,
  });
}
const env=(overrides={})=>({id:'env1',autoCost:true,ipMonthlyFee:10,ipDueDate:'2026-01-05',ipCurrency:'USD',networkName:'Net',...overrides});
const client=(overrides={})=>({id:'c1',archived:false,networkEnvironments:[env()],...overrides});

{
  let overlaps=0;const s=autoBase({clients:[client()],isMonthLocked:()=>true,clientContractOverlapsMonth:()=>{overlaps+=1;return true}});
  eq(s.ensureAutomaticAssetCosts({month:'2026-09'}),0,'locked month auto-cost returns zero');eq(overlaps,0,'locked month stops before client contract checks');eq(s.financeCosts.length,0,'locked month creates no auto cost');
}
for(const [fee,label] of [[0,'zero'],[-1,'negative'],['abc','nan'],['Infinity','infinity']]){
  let persisted=0;const s=autoBase({clients:[client({networkEnvironments:[env({ipMonthlyFee:fee})]})],persist:()=>{persisted+=1}});
  eq(s.ensureAutomaticAssetCosts({month:'2026-09',silent:false}),0,`${label} IP fee changes zero rows`);eq(s.financeCosts.length,0,`${label} IP fee creates no cost`);eq(persisted,0,`${label} IP fee does not persist`);
}
{
  let persisted=0;const notices=[];const s=autoBase({clients:[client()],persist:()=>{persisted+=1},notify:m=>notices.push(m)});
  const changed=s.ensureAutomaticAssetCosts({month:'2026-09',silent:false});
  eq(changed,1,'valid IP fee creates one row');eq(s.financeCosts.length,1,'valid IP fee row count');const row=s.financeCosts[0];
  eq(row.sourceType,'IP_ENV_MONTH','valid IP fee source type');eq(row.sourceId,'c1:env1:2026-09','valid IP fee source id');eq(row.date,'2026-09-05','valid IP fee due date');eq(row.amount,10,'valid IP fee amount');eq(row.scope,'CLIENT','valid IP fee scope');eq(row.clientId,'c1','valid IP fee client');eq(row.autoGenerated,true,'valid IP fee auto-generated marker');
  eq(persisted,1,'nonsilent changed auto-cost persists once');ok(notices.some(m=>m.includes('已同步 1 条')),'nonsilent auto-cost notification');
}
{
  let persisted=0;const existing={id:'existing',date:'2026-09-05',category:'IP',scope:'CLIENT',clientId:'c1',currency:'USD',amount:10,vendor:'Net',note:'系统自动生成 · Net 月费',sourceType:'IP_ENV_MONTH',sourceId:'c1:env1:2026-09',autoGenerated:true};
  const stale={id:'stale',date:'2026-09-01',sourceType:'IP_ENV_MONTH',sourceId:'c1:old:2026-09',autoGenerated:true};
  const otherMonth={id:'other',date:'2026-08-01',sourceType:'IP_ENV_MONTH',sourceId:'c1:old:2026-08',autoGenerated:true};
  const s=autoBase({clients:[client()],financeCosts:[existing,stale,otherMonth],persist:()=>{persisted+=1}});
  const changed=s.ensureAutomaticAssetCosts({month:'2026-09',silent:true});
  eq(changed,1,'silent auto-cost removes one stale target-month row');eq(persisted,0,'silent auto-cost never persists internally');eq(s.financeCosts.some(c=>c.id==='stale'),false,'stale target-month auto cost removed');eq(s.financeCosts.some(c=>c.id==='other'),true,'other-month auto cost preserved');eq(s.financeCosts.find(c=>c.id==='existing')?.id,'existing','matching auto cost preserves id');
}
{
  const s=autoBase({clients:[client(),client({id:'c2',networkEnvironments:[env({id:'env2'})]})]});
  const changed=s.ensureAutomaticAssetCosts({clientId:'c1',month:'2026-09',silent:true});
  eq(changed,1,'client-scoped auto-cost creates only target client row');eq(s.financeCosts.length,1,'client-scoped auto-cost row count');eq(s.financeCosts[0].clientId,'c1','client-scoped auto-cost owner');
}

// Period auto-sync delegates each period month to silent asset-cost sync and persists
// once iff any month changed. It never persists when no month changes.
{
  let nextTicks=0,persisted=0;const calls=[];
  const s=subject({financePeriodMonths:()=>['2026-08','2026-09'],$nextTick:fn=>{nextTicks+=1;fn()},ensureAutomaticAssetCosts:opts=>{calls.push(opts);return opts.month==='2026-09'?2:0},persist:()=>{persisted+=1}});
  s.syncFinancePeriodAutoCosts();eq(nextTicks,1,'period auto-sync schedules one nextTick');eq(calls.length,2,'period auto-sync visits each month');eq(calls[0].silent,true,'period auto-sync uses silent asset sync');eq(calls[1].silent,true,'period auto-sync uses silent asset sync for every month');eq(persisted,1,'period auto-sync persists once when any month changes');
}
{
  let persisted=0;const s=subject({financePeriodMonths:()=>['2026-09'],$nextTick:fn=>fn(),ensureAutomaticAssetCosts:()=>0,persist:()=>{persisted+=1}});s.syncFinancePeriodAutoCosts();eq(persisted,0,'period auto-sync skips persist when nothing changes');
}
{
  let nextTicks=0;const s=subject({financePeriodMonths:null,$nextTick:()=>{nextTicks+=1}});s.syncFinancePeriodAutoCosts();eq(nextTicks,0,'period auto-sync without period source is no-op');
}

console.log('BUSINESS_FINANCE_COST_MUTATIONS_OK: manual=finite-nonnegative+client+month-lock+upsert+durable-ACK; delete=auto-protected+lock+confirm+durable-ACK; ip-auto=finite-positive+scope+stale-cleanup+silent; period-sync=nextTick+persist-on-change');