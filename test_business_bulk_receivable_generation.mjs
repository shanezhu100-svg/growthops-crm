import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function scanBalanced(text,start,openChar,closeChar){
  if(text[start]!==openChar)throw new Error(`BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: expected ${openChar}`);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=start;i<text.length;i+=1){
    const ch=text[i],next=text[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch===openChar)depth+=1;
    else if(ch===closeChar&&--depth===0)return i;
  }
  throw new Error(`BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: unmatched ${openChar}`);
}

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*${name}\\s*\\(`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: ${name} not found`);
  const start=match.index+match[0].lastIndexOf(name);
  const paren=bundle.indexOf('(',start+name.length);
  const parenEnd=scanBalanced(bundle,paren,'(',')');
  let open=parenEnd+1; while(/\s/.test(bundle[open]||''))open+=1;
  if(bundle[open]!=='{')throw new Error(`BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: ${name} body missing`);
  const end=scanBalanced(bundle,open,'{','}');
  return bundle.slice(start,end+1).trim();
}

const names=['generateReceivablesForPeriod','ensureAutomaticReceivables','createReceivableForClientMonth'];
const methods={};
for(const name of names){
  const source=extractMethod(name);
  const compiled=vm.runInNewContext(`({${source}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
  if(typeof compiled[name]!=='function')throw new Error(`BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: ${name} not executable`);
  methods[name]=compiled[name];
}

const fail=message=>{throw new Error('BUSINESS_BULK_RECEIVABLE_GENERATION_FAILED: '+message)};
const eq=(actual,expected,message)=>{if(actual!==expected)fail(`${message}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
const ok=(value,message)=>{if(!value)fail(message)};

// A period containing any locked month is atomic: no helper call, persist, or audit.
{
  let createCalls=0,persistCount=0,auditCount=0;
  const notices=[];
  const ctx={
    financePeriodMonths(){return ['2026-08','2026-09']},
    isMonthLocked(month){return month==='2026-08'},
    clients:[{id:'a',archived:false}],financeClientFilter:'ALL',financePeriodLabel:'2026 Q3',
    createReceivableForClientMonth(){createCalls+=1;return 1},
    persist(){persistCount+=1},logAudit(){auditCount+=1},notify(message){notices.push(message)},
  };
  methods.generateReceivablesForPeriod.call(ctx);
  eq(createCalls,0,'locked period helper calls');
  eq(persistCount,0,'locked period persist');
  eq(auditCount,0,'locked period audit');
  ok(notices.some(message=>String(message).includes('月结')), 'locked period notice');
}

// Unlocked bulk generation covers the month x active-client matrix, skips archived
// clients, and explicitly opts into future-period creation.
{
  const calls=[],audits=[],notices=[];let persistCount=0;
  const ctx={
    financePeriodMonths(){return ['2026-09','2026-10']},isMonthLocked(){return false},
    clients:[{id:'a',archived:false},{id:'b',archived:false},{id:'archived',archived:true}],
    financeClientFilter:'ALL',financePeriodLabel:'Sep-Oct',
    createReceivableForClientMonth(client,month,opts){calls.push([client.id,month,opts?.allowFuture]);return 1},
    persist(){persistCount+=1},logAudit(action,detail){audits.push([action,detail])},notify(message){notices.push(message)},
  };
  methods.generateReceivablesForPeriod.call(ctx);
  eq(JSON.stringify(calls),JSON.stringify([
    ['a','2026-09',true],['b','2026-09',true],['a','2026-10',true],['b','2026-10',true]
  ]),'bulk active-client matrix');
  eq(persistCount,1,'bulk persist once');
  eq(audits.length,1,'bulk audit once');
  ok(audits[0][1].includes('新增 4 条'),'bulk audit count');
  ok(notices.some(message=>String(message).includes('4 条')),'bulk success notice');
}

// A specific finance filter limits generation to the exact client id.
{
  const calls=[];
  const ctx={
    financePeriodMonths(){return ['2026-09']},isMonthLocked(){return false},
    clients:[{id:'1',archived:false},{id:2,archived:false}],financeClientFilter:'2',financePeriodLabel:'Sep',
    createReceivableForClientMonth(client,month,opts){calls.push([String(client.id),month,opts.allowFuture]);return 1},
    persist(){},logAudit(){},notify(){},
  };
  methods.generateReceivablesForPeriod.call(ctx);
  eq(JSON.stringify(calls),JSON.stringify([['2','2026-09',true]]),'specific client filter');
}

function createContext({client={},month='2026-09',allowFuture=false,receivables=[],fee=100,locked=false,current='2026-09',scheduled='2026-09-15'}={}){
  const financeReceivables=receivables;
  let feeCalls=0,uidCalls=0;
  const ctx={
    financeReceivables,
    localDateKey(){return `${current}-02`},isMonthLocked(){return locked},
    financeServiceFeeForClientMonth(){feeCalls+=1;return fee},
    monthDueDate(){return scheduled},accountUid(){uidCalls+=1;return 'ar-new'},
    normalizeReceivable(row){return row},
  };
  const base={id:'client-1',archived:false,billingMode:'FULL_MONTH',monthlyFee:100,currency:'USD',startDate:'2026-01-01',endDate:'2026-12-31',renewalAlertDay:15,...client};
  return {ctx,client:base,month,allowFuture,get feeCalls(){return feeCalls},get uidCalls(){return uidCalls}};
}

// Duplicate service-fee receivables are idempotent across legacy/default field values.
{
  const existing={clientId:'client-1',settlementMonth:'2026-09',currency:'USD',incomeType:'SERVICE_FEE'};
  const state=createContext({receivables:[existing]});
  const added=methods.createReceivableForClientMonth.call(state.ctx,state.client,state.month,{allowFuture:false});
  eq(added,0,'duplicate added count');
  eq(state.ctx.financeReceivables.length,1,'duplicate receivable count');
  eq(state.feeCalls,0,'duplicate stops before amount calculation');
}

// Archived/manual/locked/future/outside-contract clients never create rows.
for(const scenario of [
  {label:'archived',client:{archived:true}},
  {label:'manual',client:{billingMode:'MANUAL'}},
  {label:'locked',locked:true},
  {label:'future',month:'2026-10',current:'2026-09'},
  {label:'before-start',month:'2025-12'},
  {label:'after-end',month:'2027-01'},
]){
  const state=createContext(scenario);
  const added=methods.createReceivableForClientMonth.call(state.ctx,state.client,state.month,{allowFuture:false});
  eq(added,0,`${scenario.label} added count`);
  eq(state.ctx.financeReceivables.length,0,`${scenario.label} receivable mutation`);
}

// Billing inputs and calculated service-fee amounts must be finite and positive.
// NaN/Infinity must never enter formal receivables because every downstream finance
// total assumes a real numeric amount.
for(const monthlyFee of ['not-a-number','Infinity']){
  const state=createContext({client:{monthlyFee}});
  const added=methods.createReceivableForClientMonth.call(state.ctx,state.client,state.month,{allowFuture:false});
  eq(added,0,`nonfinite monthlyFee added ${monthlyFee}`);
  eq(state.ctx.financeReceivables.length,0,`nonfinite monthlyFee mutation ${monthlyFee}`);
}
for(const fee of [NaN,Infinity,-Infinity,0,-1]){
  const state=createContext({fee});
  const added=methods.createReceivableForClientMonth.call(state.ctx,state.client,state.month,{allowFuture:false});
  eq(added,0,`invalid calculated amount added ${String(fee)}`);
  eq(state.ctx.financeReceivables.length,0,`invalid calculated amount mutation ${String(fee)}`);
}

// A valid service fee creates exactly one normalized AUTO_SERVICE_FEE row and clamps
// the first-month due date forward to the service start date when needed.
{
  const state=createContext({client:{startDate:'2026-09-20'},scheduled:'2026-09-15',fee:125.5});
  const added=methods.createReceivableForClientMonth.call(state.ctx,state.client,'2026-09',{allowFuture:false});
  eq(added,1,'valid helper added count');
  eq(state.ctx.financeReceivables.length,1,'valid helper row count');
  const row=state.ctx.financeReceivables[0];
  eq(row.amount,125.5,'valid helper amount');
  eq(row.billSource,'AUTO_SERVICE_FEE','valid helper source');
  eq(row.dueDate,'2026-09-20','first-month due date clamp');
  eq(row.directCostDate,'2026-09-01','direct cost month date');
  eq(state.uidCalls,1,'valid helper uid once');
}

// Automatic completion skips archived clients, respects exact clientId scope, and
// persists/audits only when at least one missing receivable was created.
{
  const calls=[],audits=[];let persistCount=0;
  const ctx={
    localDateKey(){return '2026-09-02'},
    clients:[{id:'a',archived:false},{id:'b',archived:false},{id:'x',archived:true}],
    clientAutoReceivableMonths(client,current){calls.push(['months',client.id,current]);return ['2026-08','2026-09']},
    createReceivableForClientMonth(client,month){calls.push(['create',client.id,month]);return month==='2026-09'?1:0},
    persist(){persistCount+=1},logAudit(action,detail){audits.push([action,detail])},notify(){},
  };
  const added=methods.ensureAutomaticReceivables.call(ctx,{clientId:'b',silent:true});
  eq(added,1,'automatic scoped added count');
  eq(JSON.stringify(calls),JSON.stringify([
    ['months','b','2026-09'],['create','b','2026-08'],['create','b','2026-09']
  ]),'automatic exact client scope');
  eq(persistCount,1,'automatic persist on addition');
  eq(audits.length,1,'automatic audit on addition');
}
{
  let persistCount=0,auditCount=0;
  const ctx={
    localDateKey(){return '2026-09-02'},clients:[{id:'a',archived:false}],
    clientAutoReceivableMonths(){return ['2026-09']},createReceivableForClientMonth(){return 0},
    persist(){persistCount+=1},logAudit(){auditCount+=1},notify(){},
  };
  const added=methods.ensureAutomaticReceivables.call(ctx,{silent:false});
  eq(added,0,'automatic no-op added');
  eq(persistCount,0,'automatic no-op persist');
  eq(auditCount,0,'automatic no-op audit');
}

console.log('BUSINESS_BULK_RECEIVABLE_GENERATION_OK: bulk=locked-atomic+active-matrix+client-filter+future-opt-in; helper=duplicate+eligibility+finite-positive+due-date; automatic=archived-skip+client-scope+persist-on-change; provenance=final-shipped-vm');