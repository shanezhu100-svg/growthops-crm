import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  'deleteFinanceCost','deleteReceivablePayment','deleteReceivable',
  'archiveClient','restoreClient','deleteLead','toggleFinanceMonthLock','voidReconciliation',
];
let methods;
try{
  methods=vm.runInNewContext(`({${names.map(extractMethod).join(',\n')}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
}catch(error){
  throw new Error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FAILED: unable to execute final methods: ${error.message}`);
}

const findings=[];
const finding=(name,detail)=>findings.push(`${name}: ${detail}`);
const subject=extra=>Object.assign({},methods,extra||{});

// 1) Manual finance cost delete: month can become locked while confirmation is open.
{
  const target={id:'cost-target',date:'2026-09-01',category:'OTHER',scope:'COMPANY',currency:'USD',amount:10};
  let action=null,persisted=0,audited=0,locked=false;
  const s=subject({
    financeCosts:[target],
    assertMonthUnlocked:()=>!locked,
    askConfirm:(_cfg,cb)=>{action=cb},
    financeCostCategoryText:()=> 'Other',formatMoney:value=>String(value),
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.deleteFinanceCost(target);
  locked=true;
  action?.();
  if(s.financeCosts.length!==1||persisted!==0||audited!==0)finding('deleteFinanceCost','confirmation callback deletes/persists after target month becomes locked');
}

// 2) Payment delete: payment month can become locked while confirmation is open.
{
  const payment={id:'pay-target',date:'2026-09-01',amount:25};
  const row={id:'recv-pay',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',incomeType:'SERVICE_FEE',payments:[payment],paidAmount:25};
  let action=null,persisted=0,audited=0,locked=false;
  const s=subject({
    financeReceivables:[row],financeCosts:[],receivableForm:null,
    assertMonthUnlocked:()=>!locked,
    askConfirm:(_cfg,cb)=>{action=cb},
    financeReceivablePaid:r=>(r.payments||[]).reduce((sum,p)=>sum+Number(p.amount||0),0),
    financeReceivableClientName:()=> 'Client',formatMoney:value=>String(value),
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.deleteReceivablePayment(row,payment);
  locked=true;
  action?.();
  if(row.payments.length!==1||persisted!==0||audited!==0)finding('deleteReceivablePayment','confirmation callback deletes payment after payment month becomes locked');
}

// 3) Receivable delete: own month or linked-cost month can become locked while confirmation is open.
{
  const row={id:'recv-target',clientId:'c1',amount:100,currency:'USD',settlementMonth:'2026-09',dueDate:'2026-09-30',incomeType:'SERVICE_FEE',projectName:'September',payments:[]};
  const linked={id:'cost-linked',sourceType:'RECEIVABLE_ITEM',sourceId:row.id,date:'2026-09-01',amount:10};
  let action=null,persisted=0,audited=0,locked=false;
  const s=subject({
    financeReceivables:[row],financeCosts:[linked],
    assertMonthUnlocked:()=>!locked,isMonthLocked:()=>locked,
    receivableLinkedCost:r=>s.financeCosts.find(cost=>cost.sourceType==='RECEIVABLE_ITEM'&&String(cost.sourceId)===String(r?.id))||null,
    financeReceivablePaid:r=>(r.payments||[]).reduce((sum,p)=>sum+Number(p.amount||0),0),
    financeReceivableClientName:()=> 'Client',financeIncomeTypeText:()=> 'Service',formatMoney:value=>String(value),
    askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.deleteReceivable(row);
  locked=true;
  action?.();
  if(s.financeReceivables.length!==1||s.financeCosts.length!==1||persisted!==0||audited!==0)finding('deleteReceivable','confirmation callback deletes receivable/linked cost after accounting state becomes locked');
}

// 4) Archive: permission can be revoked while confirmation is open.
{
  const client={id:'client-archive',name:'Archive',archived:false,status:'ACTIVE',archivedAt:''};
  let action=null,persisted=0,audited=0,allowed=true;
  const s=subject({
    clients:[client],canArchiveClients:()=>allowed,askConfirm:(_cfg,cb)=>{action=cb},
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.archiveClient(client);
  allowed=false;
  action?.();
  if(client.archived!==false||client.status!=='ACTIVE'||persisted!==0||audited!==0)finding('archiveClient','confirmation callback archives after archive permission is revoked');
}

// 5) Restore: permission can be revoked while confirmation is open.
{
  const client={id:'client-restore',name:'Restore',archived:true,status:'PAUSED',archivedAt:'2026-08-01T00:00:00.000Z'};
  let action=null,persisted=0,audited=0,allowed=true;
  const s=subject({
    clients:[client],canArchiveClients:()=>allowed,askConfirm:(_cfg,cb)=>{action=cb},
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.restoreClient(client);
  allowed=false;
  action?.();
  if(client.archived!==true||client.status!=='PAUSED'||persisted!==0||audited!==0)finding('restoreClient','confirmation callback restores after restore permission is revoked');
}

// 6) Lead delete: target can disappear while confirmation is open; stale confirm must be harmless.
{
  const target={id:'lead-target',company:'Target'};
  let action=null,persisted=0,audited=0;
  const s=subject({
    leads:[target],askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.deleteLead(target);
  s.leads=[];
  action?.();
  if(persisted!==0||audited!==0)finding('deleteLead','stale confirmation persists/audits after target lead has already disappeared');
}

// 7) Unlock: admin/finance authority can be revoked while confirmation is open.
{
  const month='2026-09';
  let action=null,persisted=0,audited=0,allowed=true;
  const s=subject({
    financeMonthLocks:{[month]:{lockedAt:'old'}},financeMonthSnapshots:{[month]:{createdAt:'old'}},
    currentUser:{role:'ADMIN',name:'Admin'},canManageFinance:()=>allowed,isMonthLocked:()=>true,
    askConfirm:(_cfg,cb)=>{action=cb},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.toggleFinanceMonthLock(month);
  allowed=false;
  s.currentUser={role:'OPS',name:'Former Admin'};
  action?.();
  if(!Object.hasOwn(s.financeMonthLocks,month)||persisted!==0||audited!==0)finding('toggleFinanceMonthLock','unlock confirmation proceeds after finance/admin authority is revoked');
}

// 8) Reconciliation void: settlement month can become locked while confirmation is open.
{
  const rec={id:'recon-target',status:'CONFIRMED',settlementMonth:'2026-09',providerId:'p1',contactId:'c1',currency:'USD'};
  const row={providerName:'Agency',contactName:'Alice',record:rec};
  let action=null,persisted=0,audited=0,locked=false;
  const s=subject({
    currentUser:{name:'Finance'},financeActualRebates:[{providerId:'p1',contactId:'c1',settlementMonth:'2026-09',currency:'USD'}],
    assertMonthUnlocked:()=>!locked,askConfirm:(_cfg,cb)=>{action=cb},
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:()=>{},
  });
  s.voidReconciliation(row);
  locked=true;
  action?.();
  if(rec.status!=='CONFIRMED'||s.financeActualRebates.length!==1||persisted!==0||audited!==0)finding('voidReconciliation','confirmation callback voids/removes rebate after settlement month becomes locked');
}

if(findings.length){
  console.error(`BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_FINDINGS: count=${findings.length}`);
  for(const item of findings)console.error(` - ${item}`);
  process.exitCode=1;
}else{
  console.log('BUSINESS_DESTRUCTIVE_CONFIRMATION_TOCTOU_PROBE_OK: destructive confirmation callbacks revalidate live authority, target identity, and finance locks');
}
