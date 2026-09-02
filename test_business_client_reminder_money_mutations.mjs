import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  if(open<0)throw new Error(`BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: ${name} opening brace missing`);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){
      if(escaped){escaped=false;continue}
      if(ch==='\\'){escaped=true;continue}
      if(ch===quote)quote='';
      continue;
    }
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;
    else if(ch==='}'){
      depth-=1;
      if(depth===0)return bundle.slice(start,i+1).trim();
    }
  }
  throw new Error(`BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: ${name} closing brace missing`);
}

const methodNames=['saveRecharge','saveRechargeReminder','saveRenewal','saveStandaloneAlert'];
const methods={};
for(const name of methodNames){
  const source=extractMethod(name);
  const compiled=vm.runInNewContext(`({${source}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
  if(typeof compiled[name]!=='function')throw new Error(`BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: ${name} not executable`);
  methods[name]=compiled[name];
}

const fail=message=>{throw new Error('BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,message)=>{if(actual!==expected)fail(`${message}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
const ok=(value,message)=>{if(!value)fail(message)};

function rechargeContext(amount,{locked=false,accountExists=true}={}){
  const account={id:'acct-1',rechargeHistory:[]};
  const notices=[],audits=[];
  let persistCount=0,lockChecks=0;
  const ctx={
    rechargeForm:{clientId:'client-1',platform:'FB',accountId:'acct-1',clientName:'Client One',accountName:'Account One',date:'2026-09-02',currency:'USD',amount,note:'topup'},
    showRechargeModal:true,
    findAccount(){return accountExists?account:null},
    assertMonthUnlocked(month){lockChecks+=1;eq(month,'2026-09','recharge lock month');return !locked},
    localDateKey(){return '2026-09-02'},
    persist(){persistCount+=1},
    logAudit(action,detail){audits.push([action,detail])},
    notify(message){notices.push(message)},
    formatMoney(value,currency){return `${currency} ${value}`},
    hasUsdBalanceData(){return false},
    accountBalanceText(){return '$0'},
  };
  return {ctx,account,notices,audits,get persistCount(){return persistCount},get lockChecks(){return lockChecks}};
}

// Valid positive recharge is persisted/audited exactly once.
{
  const state=rechargeContext('125.50');
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,1,'valid recharge row count');
  eq(state.account.rechargeHistory[0].amount,125.5,'valid recharge numeric amount');
  eq(state.persistCount,1,'valid recharge persist');
  eq(state.audits.length,1,'valid recharge audit');
  eq(state.ctx.showRechargeModal,false,'valid recharge closes modal');
}

// Locked months stop before mutation/persist/audit.
{
  const state=rechargeContext('50',{locked:true});
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,0,'locked recharge mutation');
  eq(state.persistCount,0,'locked recharge persist');
  eq(state.audits.length,0,'locked recharge audit');
  eq(state.lockChecks,1,'locked recharge lock check');
}

// Invalid numeric input must be finite and positive. NaN/Infinity must never enter
// recharge history because downstream balance math and audit text assume real money.
for(const amount of ['0','-1','not-a-number','Infinity']){
  const state=rechargeContext(amount);
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,0,`invalid recharge mutation ${amount}`);
  eq(state.persistCount,0,`invalid recharge persist ${amount}`);
  eq(state.audits.length,0,`invalid recharge audit ${amount}`);
  ok(state.notices.some(message=>String(message).includes('有效的充值金额')),`invalid recharge notice ${amount}`);
}

// Missing account remains harmless and closes the modal without persistence.
{
  const state=rechargeContext('50',{accountExists:false});
  methods.saveRecharge.call(state.ctx);
  eq(state.persistCount,0,'missing account recharge persist');
  eq(state.audits.length,0,'missing account recharge audit');
  eq(state.ctx.showRechargeModal,false,'missing account recharge modal');
}

// Recharge-reminder edits are already applied by form binding; this method persists
// exactly once for a real account and does nothing for a missing account.
{
  let persistCount=0;
  methods.saveRechargeReminder.call({persist(){persistCount+=1}},{id:'acct-1'});
  eq(persistCount,1,'recharge reminder persist');
  methods.saveRechargeReminder.call({persist(){persistCount+=1}},null);
  eq(persistCount,1,'missing recharge reminder no-op');
}

function renewalContext({target,standaloneAlerts=[],clients=[],dismissedAlerts=[]}){
  const notices=[],audits=[],autoBillCalls=[];
  let persistCount=0;
  const ctx={
    renewalTarget:target,
    renewalForm:{newDueDate:'2026-12-31',note:'renewed'},
    standaloneAlerts,
    clients,
    dismissedAlerts,
    showRenewalModal:true,
    localDateKey(){return '2026-09-02'},
    syncLegacyNetworkFields(){},
    ensureAutomaticReceivables(args){autoBillCalls.push(args);return 2},
    persist(){persistCount+=1},
    logAudit(action,detail){audits.push([action,detail])},
    notify(message){notices.push(message)},
    alertTypeName(key){return key},
  };
  return {ctx,notices,audits,autoBillCalls,get persistCount(){return persistCount}};
}

// Existing standalone alert renewal updates exactly that alert and clears its dismissal.
{
  const alert={id:'sa-1',dueDate:'2026-10-01'};
  const target={id:'sa-1',isStandalone:true,dueDate:'2026-10-01',clientName:'Manual',type:'IP'};
  const state=renewalContext({target,standaloneAlerts:[alert],dismissedAlerts:[{id:'sa-1'},{id:'keep'}]});
  methods.saveRenewal.call(state.ctx);
  eq(alert.dueDate,'2026-12-31','standalone renewal date');
  eq(state.ctx.dismissedAlerts.length,1,'standalone renewal dismissal cleanup');
  eq(state.ctx.dismissedAlerts[0].id,'keep','standalone renewal unrelated dismissal');
  eq(state.persistCount,1,'standalone renewal persist');
  eq(state.audits.length,1,'standalone renewal audit');
  eq(state.autoBillCalls.length,0,'standalone renewal auto billing');
}

// A stale standalone renewal target must fail closed. It may not erase dismissed state
// or emit a successful persisted/audited renewal when the source reminder is gone.
{
  const target={id:'sa-missing',isStandalone:true,dueDate:'2026-10-01',clientName:'Manual',type:'IP'};
  const state=renewalContext({target,standaloneAlerts:[],dismissedAlerts:[{id:'sa-missing'}]});
  methods.saveRenewal.call(state.ctx);
  eq(state.ctx.dismissedAlerts.length,1,'stale standalone dismissal preserved');
  eq(state.persistCount,0,'stale standalone renewal persist');
  eq(state.audits.length,0,'stale standalone renewal audit');
  eq(state.autoBillCalls.length,0,'stale standalone renewal auto billing');
  eq(state.ctx.showRenewalModal,true,'stale standalone renewal form preserved');
  ok(state.notices.some(message=>String(message).includes('不存在')||String(message).includes('刷新')), 'stale standalone renewal notice');
}

// Normal contract renewal updates endDate/history, triggers receivable completion, and
// persists/audits once.
{
  const client={id:'client-1',endDate:'2026-10-01',renewalHistory:[]};
  const target={id:'contract-client-1',isStandalone:false,typeKey:'CONTRACT',dueDate:'2026-10-01',clientId:'client-1',clientName:'Client One',type:'合同'};
  const state=renewalContext({target,clients:[client],dismissedAlerts:[{id:'contract-client-1'}]});
  methods.saveRenewal.call(state.ctx);
  eq(client.endDate,'2026-12-31','contract renewal end date');
  eq(client.renewalHistory.length,1,'contract renewal history');
  eq(state.autoBillCalls.length,1,'contract renewal auto billing');
  eq(state.persistCount,1,'contract renewal persist');
  eq(state.audits.length,1,'contract renewal audit');
}

// A stale contract modal must not overwrite a newer endDate or create receivables.
{
  const client={id:'client-1',endDate:'2027-01-31',renewalHistory:[]};
  const target={id:'contract-client-1',isStandalone:false,typeKey:'CONTRACT',dueDate:'2026-10-01',clientId:'client-1',clientName:'Client One',type:'合同'};
  const state=renewalContext({target,clients:[client],dismissedAlerts:[{id:'contract-client-1'}]});
  methods.saveRenewal.call(state.ctx);
  eq(client.endDate,'2027-01-31','stale contract end date preserved');
  eq(client.renewalHistory.length,0,'stale contract renewal history');
  eq(state.ctx.dismissedAlerts.length,1,'stale contract dismissal preserved');
  eq(state.autoBillCalls.length,0,'stale contract no auto billing');
  eq(state.persistCount,0,'stale contract renewal persist');
  eq(state.audits.length,0,'stale contract renewal audit');
  eq(state.ctx.showRenewalModal,true,'stale contract renewal form preserved');
  ok(state.notices.some(message=>String(message).includes('变化')||String(message).includes('刷新')), 'stale contract renewal notice');
}

// Standalone alert creation still enforces a known type and a non-empty due date.
{
  let persistCount=0,auditCount=0;
  const ctx={
    reminderTypeOptions:[{key:'IP'}],newAlertForm:{typeKey:'UNKNOWN',clientName:'X',dueDate:'2026-10-01',cost:'',target:''},standaloneAlerts:[],showAddAlertModal:true,
    persist(){persistCount+=1},logAudit(){auditCount+=1},notify(){},
  };
  methods.saveStandaloneAlert.call(ctx);
  eq(ctx.standaloneAlerts.length,0,'invalid standalone alert type');
  eq(persistCount,0,'invalid standalone alert persist');
  eq(auditCount,0,'invalid standalone alert audit');
}

console.log('BUSINESS_CLIENT_REMINDER_MONEY_MUTATIONS_OK: recharge=finite-positive+month-lock+account-scope; recharge-reminder=persist-only; renewal=standalone+contract+stale-fail-closed+auto-billing; standalone-alert=type-guard; persist+audit=phase-pinned');