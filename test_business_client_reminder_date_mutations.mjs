import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
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
  throw new Error(`BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: ${name} closing brace missing`);
}

const methods={};
for(const name of ['saveRecharge','saveRenewal','saveStandaloneAlert']){
  const source=extractMethod(name);
  const compiled=vm.runInNewContext(`({${source}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
  if(typeof compiled[name]!=='function')throw new Error(`BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: ${name} not executable`);
  methods[name]=compiled[name];
}

const fail=message=>{throw new Error('BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,message)=>{if(actual!==expected)fail(`${message}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`)};
const ok=(value,message)=>{if(!value)fail(message)};

function rechargeState(date){
  const account={id:'acct-1',rechargeHistory:[]},notices=[],audits=[],lockMonths=[];
  let persistCount=0;
  const ctx={
    rechargeForm:{clientId:'client-1',platform:'FB',accountId:'acct-1',clientName:'Client One',accountName:'Account One',date,currency:'USD',amount:'10',note:''},
    showRechargeModal:true,
    findAccount(){return account},
    assertMonthUnlocked(month){lockMonths.push(month);return true},
    localDateKey(){return '2026-09-02'},
    persist(){persistCount+=1},
    logAudit(action,detail){audits.push([action,detail])},
    notify(message){notices.push(message)},
    formatMoney(value,currency){return `${currency} ${value}`},
    hasUsdBalanceData(){return false},
    accountBalanceText(){return '$0'},
  };
  return {ctx,account,notices,audits,lockMonths,get persistCount(){return persistCount}};
}

for(const date of ['2026-02-30','2026/09/02','not-a-date']){
  const state=rechargeState(date);
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,0,`invalid recharge date mutation ${date}`);
  eq(state.lockMonths.length,0,`invalid recharge date lock check ${date}`);
  eq(state.persistCount,0,`invalid recharge date persist ${date}`);
  eq(state.audits.length,0,`invalid recharge date audit ${date}`);
  ok(state.notices.some(message=>String(message).includes('日期')),`invalid recharge date notice ${date}`);
}
{
  const state=rechargeState('');
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,1,'blank recharge date defaults to local date');
  eq(state.account.rechargeHistory[0].date,'2026-09-02','blank recharge default date value');
  eq(state.lockMonths[0],'2026-09','blank recharge default lock month');
}
{
  const state=rechargeState('2028-02-29');
  methods.saveRecharge.call(state.ctx);
  eq(state.account.rechargeHistory.length,1,'leap recharge date accepted');
  eq(state.account.rechargeHistory[0].date,'2028-02-29','leap recharge date preserved');
  eq(state.lockMonths[0],'2028-02','leap recharge lock month');
}

function renewalState(newDueDate){
  const notices=[],audits=[],autoBillCalls=[];
  let persistCount=0;
  const client={id:'client-1',endDate:'2026-01-01',renewalHistory:[]};
  const target={id:'contract-client-1',isStandalone:false,typeKey:'CONTRACT',dueDate:'2026-01-01',clientId:'client-1',clientName:'Client One',type:'合同'};
  const ctx={
    renewalTarget:target,
    renewalForm:{newDueDate,note:''},
    standaloneAlerts:[],clients:[client],dismissedAlerts:[{id:target.id}],showRenewalModal:true,
    localDateKey(){return '2026-09-02'},
    syncLegacyNetworkFields(){},
    ensureAutomaticReceivables(args){autoBillCalls.push(args);return 1},
    persist(){persistCount+=1},
    logAudit(action,detail){audits.push([action,detail])},
    notify(message){notices.push(message)},
    alertTypeName(key){return key},
  };
  return {ctx,client,notices,audits,autoBillCalls,get persistCount(){return persistCount}};
}

for(const date of ['2026-02-30','2026/12/31','not-a-date']){
  const state=renewalState(date);
  methods.saveRenewal.call(state.ctx);
  eq(state.client.endDate,'2026-01-01',`invalid renewal date mutation ${date}`);
  eq(state.client.renewalHistory.length,0,`invalid renewal history ${date}`);
  eq(state.ctx.dismissedAlerts.length,1,`invalid renewal dismissal ${date}`);
  eq(state.autoBillCalls.length,0,`invalid renewal auto billing ${date}`);
  eq(state.persistCount,0,`invalid renewal persist ${date}`);
  eq(state.audits.length,0,`invalid renewal audit ${date}`);
  ok(state.notices.some(message=>String(message).includes('日期')),`invalid renewal date notice ${date}`);
}
{
  const state=renewalState('2028-02-29');
  methods.saveRenewal.call(state.ctx);
  eq(state.client.endDate,'2028-02-29','leap renewal date accepted');
  eq(state.client.renewalHistory.length,1,'leap renewal history');
  eq(state.autoBillCalls.length,1,'leap renewal auto billing');
  eq(state.persistCount,1,'leap renewal persist');
  eq(state.audits.length,1,'leap renewal audit');
}

function standaloneState(dueDate){
  const notices=[],audits=[];
  let persistCount=0;
  const ctx={
    reminderTypeOptions:[{key:'IP'}],
    newAlertForm:{typeKey:'IP',clientName:'Manual',dueDate,cost:'',target:''},
    standaloneAlerts:[],showAddAlertModal:true,
    persist(){persistCount+=1},
    logAudit(action,detail){audits.push([action,detail])},
    notify(message){notices.push(message)},
  };
  return {ctx,notices,audits,get persistCount(){return persistCount}};
}

for(const date of ['2026-02-30','2026/12/31','not-a-date']){
  const state=standaloneState(date);
  methods.saveStandaloneAlert.call(state.ctx);
  eq(state.ctx.standaloneAlerts.length,0,`invalid standalone date mutation ${date}`);
  eq(state.persistCount,0,`invalid standalone date persist ${date}`);
  eq(state.audits.length,0,`invalid standalone date audit ${date}`);
  ok(state.notices.some(message=>String(message).includes('日期')),`invalid standalone date notice ${date}`);
}
{
  const state=standaloneState('2028-02-29');
  methods.saveStandaloneAlert.call(state.ctx);
  eq(state.ctx.standaloneAlerts.length,1,'leap standalone date accepted');
  eq(state.ctx.standaloneAlerts[0].dueDate,'2028-02-29','leap standalone date preserved');
  eq(state.persistCount,1,'leap standalone persist');
  eq(state.audits.length,1,'leap standalone audit');
}

console.log('BUSINESS_CLIENT_REMINDER_DATE_MUTATIONS_OK: recharge+renewal+standalone=yyyy-mm-dd+calendar-valid; recharge-empty=local-default; leap-day=accepted; invalid=denied-before-mutation+persist+audit');