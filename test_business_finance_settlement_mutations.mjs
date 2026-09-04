import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const methodNames=['toggleFinanceMonthLock','runFinanceMonthCheck','saveReconciliation','voidReconciliation'];
let methods;
try{methods=vm.runInNewContext(`({${methodNames.map(extractMethod).join(',\n')}})`,Object.create(null),{timeout:1000})}
catch(error){throw new Error(`BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: unable to execute final runtime methods: ${error.message}`)}
for(const name of methodNames)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: ${name} is not executable`);

const fail=message=>{throw new Error('BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const ok=(value,label)=>{if(!value)fail(label)};
const makeSubject=extra=>Object.assign({},methods,extra||{});

// Month check remains the settlement preflight authority: automatic asset costs are
// refreshed/persisted before the current check result is returned.
{
  const ensured=[]; let persisted=0; const notifications=[];
  const check={issues:['缺少返点']};
  const s=makeSubject({
    ensureAutomaticAssetCosts:opts=>ensured.push(opts),persist:()=>{persisted+=1},
    getFinanceMonthCheck:month=>{eq(month,'2026-08','month check lookup month');return check},
    notify:message=>notifications.push(message),
  });
  const result=s.runFinanceMonthCheck('2026-08');
  eq(result,check,'month check returns underlying result');
  eq(ensured.length,1,'month check refreshes automatic asset costs once');
  eq(ensured[0].month,'2026-08','month check asset refresh month');
  eq(ensured[0].silent,true,'month check asset refresh is silent');
  eq(persisted,1,'month check persists refreshed automatic costs');
  ok(notifications.some(message=>message.includes('月结检查未通过')),'month check issue notification missing');
}

// Keep one settlement-level lock preflight assertion here; detailed lock/unlock ACK,
// rollback and concurrency behavior is owned by test_business_finance_month_lock_persistence_ack.mjs.
{
  let lockChecks=0,confirms=0,persisted=0; let notified='';
  const s=makeSubject({
    canManageFinance:()=>false,isMonthLocked:()=>{lockChecks+=1;return false},
    askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},notify:message=>{notified=message},
  });
  s.toggleFinanceMonthLock('2026-08');
  eq(lockChecks,0,'unauthorized month toggle stops before lock lookup');
  eq(confirms,0,'unauthorized month toggle must not confirm');
  eq(persisted,0,'unauthorized month toggle must not persist');
  ok(notified.includes('无财务月结权限'),'unauthorized month toggle notification missing');
}

// Reconciliation save validates required selection/month and amount bounds before any
// accounting mutation. Locked months remain immutable.
{
  let lockChecks=0,persisted=0; let notified='';
  const s=makeSubject({
    reconciliationForm:{settlementMonth:''},reconciliationSelectedOption:null,
    assertMonthUnlocked:()=>{lockChecks+=1;return true},persist:()=>{persisted+=1},notify:message=>{notified=message},
  });
  s.saveReconciliation();
  eq(lockChecks,0,'missing reconciliation selection/month stops before month-lock check');
  eq(persisted,0,'missing reconciliation selection/month must not persist');
  ok(notified.includes('请选择开户商'),'missing reconciliation selection notification missing');
}
{
  let persisted=0,accountIds=0; const notifications=[];
  const option={providerId:'p1',contactId:'c1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const s=makeSubject({
    reconciliationForm:{settlementMonth:'2026-08',confirmedSpend:'-1',actualRebate:'10',currency:'USD'},
    reconciliationSelectedOption:option,financeReconciliations:[],financeActualRebates:[],
    assertMonthUnlocked:()=>true,accountUid:()=>{accountIds+=1;return 'new'},persist:()=>{persisted+=1},notify:message=>notifications.push(message),
  });
  s.saveReconciliation();
  eq(accountIds,0,'invalid reconciliation amounts stop before id allocation');
  eq(persisted,0,'invalid reconciliation amounts must not persist');
  eq(s.financeReconciliations.length,0,'invalid reconciliation amounts must not mutate records');
  ok(notifications.some(message=>message.includes('有效的确认消耗和返点')),'invalid reconciliation amount notification missing');
}
{
  let persisted=0,audited=0;
  const option={providerId:'p1',contactId:'c1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const s=makeSubject({
    reconciliationForm:{settlementMonth:'2026-08',confirmedSpend:'100',actualRebate:'10',currency:'USD'},
    reconciliationSelectedOption:option,financeReconciliations:[],financeActualRebates:[],
    assertMonthUnlocked:()=>false,accountUid:()=> 'new',persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.saveReconciliation();
  eq(persisted,0,'locked reconciliation save must not persist');
  eq(audited,0,'locked reconciliation save must not audit');
  eq(s.financeReconciliations.length,0,'locked reconciliation save must not mutate records');
}

// A valid insert and matching-key update preserve the original settlement business
// semantics but durable success now crosses the explicit cloud ACK barrier instead
// of calling the debounced persist path directly.
{
  const option={providerId:'p1',contactId:'c1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const unrelated={providerId:'p2',contactId:'c2',settlementMonth:'2026-08',currency:'USD',actualRebate:3};
  let persisted=0,barrierCalls=0; const audited=[]; const notifications=[];
  const s=makeSubject({
    reconciliationForm:{id:'',settlementMonth:'2026-08',currency:'USD',confirmedSpend:'100.5',actualRebate:'12.5',confirmedDate:'',note:'checked'},
    reconciliationSelectedOption:option,reconciliationSystemSpend:98,reconciliationExpectedRebate:11,
    financeReconciliations:[],financeActualRebates:[{providerId:'p1',contactId:'c1',settlementMonth:'2026-08',currency:'USD',actualRebate:9},unrelated],
    auditLogs:[],showReconciliationModal:true,
    assertMonthUnlocked:()=>true,accountUid:type=>{eq(type,'recon','reconciliation id prefix');return 'recon-new'},
    localDateKey:()=> '2026-09-01',formatMoney:(value,currency)=>`${currency}:${value}`,
    persist:()=>{persisted+=1},persistReconciliationBarrier:async()=>{barrierCalls+=1},
    logAudit:(action,target)=>{const row={action,target};audited.push([action,target]);s.auditLogs.push(row);return row},
    notify:message=>notifications.push(message),
  });
  await s.saveReconciliation();
  eq(s.financeReconciliations.length,1,'new reconciliation inserts one row');
  const rec=s.financeReconciliations[0];
  eq(rec.id,'recon-new','new reconciliation id');
  eq(rec.status,'CONFIRMED','new reconciliation confirmed status');
  eq(rec.confirmedSpend,100.5,'new reconciliation confirmed spend numeric normalization');
  eq(rec.actualRebate,12.5,'new reconciliation actual rebate numeric normalization');
  eq(rec.systemSpend,98,'new reconciliation stores system spend snapshot');
  eq(rec.expectedRebate,11,'new reconciliation stores expected rebate snapshot');
  eq(rec.confirmedDate,'2026-09-01','new reconciliation defaults confirmed date');
  eq(s.financeActualRebates.length,1,'new reconciliation removes superseded matching actual rebate only');
  eq(s.financeActualRebates[0],unrelated,'new reconciliation preserves unrelated actual rebate');
  eq(s.showReconciliationModal,false,'successful reconciliation closes modal after ACK');
  eq(barrierCalls,1,'successful reconciliation durable barrier count');
  eq(persisted,0,'successful reconciliation uses ACK barrier instead of debounced persist');
  eq(audited.length,1,'successful reconciliation audit count');
  eq(audited[0][0],'代理商返点对账','successful reconciliation audit action');
  ok(notifications.some(message=>message.includes('对账已确认')),'successful reconciliation notification missing');
}
{
  const option={providerId:'p1',contactId:'c1',provider:{name:'Agency'},contact:{name:'Alice'}};
  const existing={id:'stable-id',providerId:'p1',contactId:'c1',settlementMonth:'2026-08',currency:'USD',confirmedSpend:1,actualRebate:1,status:'CONFIRMED'};
  let persisted=0,barrierCalls=0;
  const s=makeSubject({
    reconciliationForm:{settlementMonth:'2026-08',currency:'USD',confirmedSpend:'200',actualRebate:'20',confirmedDate:'2026-08-31',note:''},
    reconciliationSelectedOption:option,reconciliationSystemSpend:190,reconciliationExpectedRebate:19,
    financeReconciliations:[existing],financeActualRebates:[],auditLogs:[],showReconciliationModal:true,
    assertMonthUnlocked:()=>true,accountUid:()=> 'discarded-new-id',localDateKey:()=> '2026-09-01',formatMoney:value=>String(value),
    persist:()=>{persisted+=1},persistReconciliationBarrier:async()=>{barrierCalls+=1},
    logAudit:(action,target)=>{const row={action,target};s.auditLogs.push(row);return row},notify:()=>{},
  });
  await s.saveReconciliation();
  eq(s.financeReconciliations.length,1,'matching reconciliation updates instead of duplicating');
  eq(s.financeReconciliations[0].id,'stable-id','matching reconciliation preserves existing id');
  eq(s.financeReconciliations[0].confirmedSpend,200,'matching reconciliation updates confirmed spend');
  eq(s.financeReconciliations[0].actualRebate,20,'matching reconciliation updates actual rebate');
  eq(barrierCalls,1,'matching reconciliation update durable barrier count');
  eq(persisted,0,'matching reconciliation update uses ACK barrier');
}

// Void remains live-record + month-lock + confirmation gated. Once confirmed, the
// accounting mutation and audit become successful only after the same durable ACK.
{
  let lockChecks=0,confirms=0;
  const s=makeSubject({assertMonthUnlocked:()=>{lockChecks+=1;return true},askConfirm:()=>{confirms+=1}});
  s.voidReconciliation(null);
  s.voidReconciliation({record:{status:'VOID'}});
  eq(lockChecks,0,'missing/already-void reconciliation stops before month-lock check');
  eq(confirms,0,'missing/already-void reconciliation must not confirm');
}
{
  const row={providerName:'Agency',contactName:'Alice',record:{id:'r1',status:'CONFIRMED',settlementMonth:'2026-08',providerId:'p1',contactId:'c1',currency:'USD'}};
  let confirms=0,persisted=0;
  const s=makeSubject({assertMonthUnlocked:()=>false,askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},financeActualRebates:[]});
  s.voidReconciliation(row);
  eq(row.record.status,'CONFIRMED','locked void keeps reconciliation status');
  eq(confirms,0,'locked void must not open confirmation');
  eq(persisted,0,'locked void must not persist');
}
{
  const rec={id:'r1',status:'CONFIRMED',settlementMonth:'2026-08',providerId:'p1',contactId:'c1',currency:'USD'};
  const row={providerName:'Agency',contactName:'Alice',record:rec};
  const unrelated={providerId:'p2',contactId:'c2',settlementMonth:'2026-08',currency:'USD'};
  let confirmConfig=null,confirmAction=null,persisted=0,barrierCalls=0; const audited=[]; const notifications=[];
  const s=makeSubject({
    currentUser:{name:'Finance User'},financeReconciliations:[rec],auditLogs:[],
    financeActualRebates:[{providerId:'p1',contactId:'c1',settlementMonth:'2026-08',currency:'USD'},unrelated],
    assertMonthUnlocked:()=>true,askConfirm:(config,action)=>{confirmConfig=config;confirmAction=action},
    persist:()=>{persisted+=1},persistReconciliationBarrier:async()=>{barrierCalls+=1},
    logAudit:(action,target)=>{const audit={action,target};audited.push([action,target]);s.auditLogs.push(audit);return audit},
    notify:message=>notifications.push(message),
  });
  s.voidReconciliation(row);
  eq(rec.status,'CONFIRMED','void must not mutate before confirmation');
  eq(persisted,0,'void must not persist before confirmation');
  eq(confirmConfig?.title,'撤销返点对账','void confirmation title');
  ok(typeof confirmAction==='function','void confirmation callback missing');
  await confirmAction();
  eq(rec.status,'VOID','confirmed void marks record VOID');
  eq(rec.voidedBy,'Finance User','confirmed void records actor');
  ok(/^\d{4}-\d{2}-\d{2}T/.test(rec.voidedAt),'confirmed void must record ISO voidedAt');
  eq(s.financeActualRebates.length,1,'confirmed void removes matching actual rebate only');
  eq(s.financeActualRebates[0],unrelated,'confirmed void preserves unrelated actual rebate');
  eq(barrierCalls,1,'confirmed void durable barrier count');
  eq(persisted,0,'confirmed void uses ACK barrier instead of debounced persist');
  eq(audited.length,1,'confirmed void audit count');
  eq(audited[0][0],'撤销代理商返点对账','confirmed void audit action');
  ok(String(audited[0][1]).includes('Agency / Alice'),'confirmed void audit target identifies provider/contact');
  ok(notifications.some(message=>message.includes('对账已撤销')),'confirmed void notification missing');
}

console.log('BUSINESS_FINANCE_SETTLEMENT_MUTATIONS_OK: month-check=asset-refresh+persist; month-lock=permission-gate; reconciliation=lock+numeric-guard+upsert+rebate-replace+cloud-ack; void=live+lock+confirmation+rebate-remove+cloud-ack; durable-success=ACK-pinned');
