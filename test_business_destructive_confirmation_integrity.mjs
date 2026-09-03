import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['deleteFinanceCost','deleteReceivablePayment','deleteReceivable','archiveClient','restoreClient','deleteLead','toggleFinanceMonthLock','voidReconciliation'];
let methods;
try{methods=vm.runInNewContext(`({${names.map(extractMethod).join(',\n')}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});}
catch(error){throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: unable to execute final methods: ${error.message}`);}
const fail=message=>{throw new Error('BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const makeSubject=extra=>Object.assign({},methods,extra||{});

// Manual finance cost deletion must re-check the live target month at confirmation time.
{
  const target={id:'cost-target',date:'2026-09-01',category:'OTHER',scope:'COMPANY',currency:'USD',amount:10};
  let action=null,persisted=0,audited=0,locked=false;
  const s=makeSubject({financeCosts:[target],assertMonthUnlocked:()=>!locked,askConfirm:(_cfg,cb)=>{action=cb},financeCostCategoryText:()=> 'Other',formatMoney:value=>String(value),persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.deleteFinanceCost(target);locked=true;action?.();
  eq(s.financeCosts.length,1,'locked-at-confirm finance cost must survive');eq(persisted,0,'locked-at-confirm finance cost must not persist');eq(audited,0,'locked-at-confirm finance cost must not audit');
}

// Payment deletion must re-resolve the live payment and re-check its accounting month.
{
  const payment={id:'pay-target',date:'2026-09-01',amount:25};
  const row={id:'recv-pay',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',incomeType:'SERVICE_FEE',payments:[payment],paidAmount:25};
  let action=null,persisted=0,audited=0,locked=false;
  const s=makeSubject({financeReceivables:[row],financeCosts:[],receivableForm:null,assertMonthUnlocked:()=>!locked,askConfirm:(_cfg,cb)=>{action=cb},financeReceivablePaid:r=>(r.payments||[]).reduce((sum,p)=>sum+Number(p.amount||0),0),financeReceivableClientName:()=> 'Client',formatMoney:value=>String(value),normalizeReceivable:r=>({...r}),persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.deleteReceivablePayment(row,payment);locked=true;action?.();
  eq(row.payments.length,1,'locked-at-confirm payment must survive');eq(persisted,0,'locked-at-confirm payment must not persist');eq(audited,0,'locked-at-confirm payment must not audit');
}

// Receivable deletion must repeat settlement/payment/linked-cost checks when confirmed.
{
  const row={id:'recv-target',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',dueDate:'2026-09-30',incomeType:'SERVICE_FEE',projectName:'September',payments:[]};
  const linked={id:'cost-linked',sourceType:'RECEIVABLE_ITEM',sourceId:row.id,date:'2026-09-01',amount:10};
  let action=null,persisted=0,audited=0,locked=false;
  const s=makeSubject({financeReceivables:[row],financeCosts:[linked],assertMonthUnlocked:()=>!locked,isMonthLocked:()=>locked,receivableLinkedCost:r=>s.financeCosts.find(cost=>cost.sourceType==='RECEIVABLE_ITEM'&&String(cost.sourceId)===String(r?.id))||null,financeReceivablePaid:r=>(r.payments||[]).reduce((sum,p)=>sum+Number(p.amount||0),0),financeReceivableClientName:()=> 'Client',financeIncomeTypeText:()=> 'Service',formatMoney:value=>String(value),askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.deleteReceivable(row);locked=true;action?.();
  eq(s.financeReceivables.length,1,'locked-at-confirm receivable must survive');eq(s.financeCosts.length,1,'locked-at-confirm linked cost must survive');eq(persisted,0,'locked-at-confirm receivable must not persist');eq(audited,0,'locked-at-confirm receivable must not audit');
}

// Client lifecycle permission is authority at execution time, not only dialog-open time.
{
  const client={id:'client-archive',name:'Archive',archived:false,status:'ACTIVE',archivedAt:''};
  let action=null,persisted=0,audited=0,allowed=true;
  const s=makeSubject({clients:[client],canArchiveClients:()=>allowed,askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.archiveClient(client);allowed=false;action?.();
  eq(client.archived,false,'permission-revoked archive must not archive');eq(client.status,'ACTIVE','permission-revoked archive status');eq(persisted,0,'permission-revoked archive persist');eq(audited,0,'permission-revoked archive audit');
}
{
  const client={id:'client-restore',name:'Restore',archived:true,status:'PAUSED',archivedAt:'2026-08-01T00:00:00.000Z'};
  let action=null,persisted=0,audited=0,allowed=true;
  const s=makeSubject({clients:[client],canArchiveClients:()=>allowed,askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.restoreClient(client);allowed=false;action?.();
  eq(client.archived,true,'permission-revoked restore must remain archived');eq(client.status,'PAUSED','permission-revoked restore status');eq(persisted,0,'permission-revoked restore persist');eq(audited,0,'permission-revoked restore audit');
}

// A stale lead confirmation must be a no-op, not a success persist/audit.
{
  const target={id:'lead-target',company:'Target'};
  let action=null,persisted=0,audited=0;
  const s=makeSubject({leads:[target],askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.deleteLead(target);s.leads=[];action?.();
  eq(persisted,0,'stale lead confirmation persist');eq(audited,0,'stale lead confirmation audit');
}

// Unlock authority must still be ADMIN + finance-capable when the user confirms.
{
  const month='2026-09';
  let action=null,persisted=0,audited=0,allowed=true;
  const s=makeSubject({financeMonthLocks:{[month]:{lockedAt:'old'}},financeMonthSnapshots:{[month]:{createdAt:'old'}},currentUser:{role:'ADMIN',name:'Admin'},canManageFinance:()=>allowed,isMonthLocked:()=>true,askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.toggleFinanceMonthLock(month);allowed=false;s.currentUser={role:'OPS',name:'Former Admin'};action?.();
  eq(Object.hasOwn(s.financeMonthLocks,month),true,'permission-revoked unlock must keep lock');eq(Object.hasOwn(s.financeMonthSnapshots,month),true,'permission-revoked unlock must keep snapshot');eq(persisted,0,'permission-revoked unlock persist');eq(audited,0,'permission-revoked unlock audit');
}

// Reconciliation void must honor a month lock that appears while confirmation is open.
{
  const rec={id:'recon-target',status:'CONFIRMED',settlementMonth:'2026-09',providerId:'p1',contactId:'c1',currency:'USD'};
  const row={providerName:'Agency',contactName:'Alice',record:rec};
  let action=null,persisted=0,audited=0,locked=false;
  const s=makeSubject({financeReconciliations:[rec],currentUser:{name:'Finance'},financeActualRebates:[{providerId:'p1',contactId:'c1',settlementMonth:'2026-09',currency:'USD'}],assertMonthUnlocked:()=>!locked,askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{}});
  s.voidReconciliation(row);locked=true;action?.();
  eq(rec.status,'CONFIRMED','locked-at-confirm reconciliation must remain confirmed');eq(s.financeActualRebates.length,1,'locked-at-confirm actual rebate must remain');eq(persisted,0,'locked-at-confirm void persist');eq(audited,0,'locked-at-confirm void audit');
}

console.log('BUSINESS_DESTRUCTIVE_CONFIRMATION_INTEGRITY_OK: finance-cost+payment+receivable=confirm-time-live-lock; client-lifecycle=confirm-time-permission+live-state; lead-delete=live-id; month-unlock=live-authority; reconciliation-void=live-status+lock; stale=zero-persist-audit');
