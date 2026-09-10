import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd(),appDir=path.join(root,'dist','app'),adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort(),bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const adapter=fs.readFileSync(adapterPath,'utf8');
if(!adapter.includes('vm.persistRechargeBarrier=()=>flushSave();'))throw new Error('BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: recharge barrier is not wired to shared flushSave');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m'),match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('saveRecharge')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise,Error},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: final saveRecharge not executable: ${error.message}`)}

const clone=v=>JSON.parse(JSON.stringify(v));
const fail=m=>{throw new Error('BUSINESS_RECHARGE_PERSISTENCE_ACK_FAILED: '+m)};
const ok=(v,m)=>{if(!v)fail(m)};
const eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
const same=(a,b,m)=>{if(JSON.stringify(a)!==JSON.stringify(b))fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
function deferred(){let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return{promise,resolve,reject}}

function make({barrier='deferred',amount='125.50',date='2026-09-02',locked=false,accountExists=true}={}){
  const gate=deferred(),calls={barrier:0,persist:0,notify:[],audit:0},account={id:'acct-1',rechargeHistory:[]},client={id:'client-1',fbAccounts:accountExists?[account]:[],tkAccounts:[]};
  const subject={
    ...methods,
    clients:[client],
    rechargeForm:{clientId:'client-1',platform:'FB',accountId:'acct-1',clientName:'Client One',accountName:'Account One',date,currency:'USD',amount,note:'topup'},
    showRechargeModal:true,
    auditLogs:[{id:'audit-existing',action:'EXISTING'}],
    findAccount(clientId,platform,accountId){const c=this.clients.find(x=>String(x.id)===String(clientId));if(!c)return null;const rows=platform==='FB'?(c.fbAccounts||[]):(c.tkAccounts||[]);return rows.find(x=>String(x.id)===String(accountId))||null},
    assertMonthUnlocked(month){calls.lockMonth=month;return !locked},
    localDateKey(){return '2026-09-02'},
    persist(){calls.persist+=1},
    persistRechargeBarrier(){calls.barrier+=1;if(barrier==='ok')return Promise.resolve(true);if(barrier==='fail')return Promise.reject(new Error('SYNTHETIC_RECHARGE_SAVE_FAILED'));return gate.promise},
    logAudit(action,target){calls.audit+=1;const row={id:`audit-${calls.audit}`,action:String(action),target:String(target)};this.auditLogs.push(row);return row},
    notify(message){calls.notify.push(String(message))},
    formatMoney(value,currency){return `${currency} ${Number(value)}`},
    hasUsdBalanceData(){return false},
    accountBalanceText(){return '$0'},
  };
  return{subject,client,account,calls,gate};
}

// Successful recharge is tentative until the shared cloud queue acknowledges it.
{
  const {subject,account,calls,gate}=make(),task=subject.saveRecharge();
  ok(task&&typeof task.then==='function','valid recharge returns ACK promise');
  eq(calls.barrier,1,'valid recharge crosses barrier once');
  eq(calls.persist,0,'legacy persist suppressed before ACK');
  eq(account.rechargeHistory.length,1,'tentative recharge row exists before ACK');
  eq(account.rechargeHistory[0].amount,125.5,'recharge amount normalized');
  eq(subject.showRechargeModal,true,'recharge modal stays open before ACK');
  eq(calls.notify.length,0,'success notice held before ACK');
  gate.resolve(true);await task;
  eq(subject.showRechargeModal,false,'modal closes after ACK');
  ok(calls.notify.some(m=>m.includes('广告充值已登记')),'success notice emitted after ACK');
  eq(calls.persist,0,'successful recharge never uses legacy debounced persist');
  eq(calls.audit,1,'successful recharge audits once');
}

// Failed ACK removes only the attempt row/audit, reopens no changed UI, and persists rollback truth.
{
  const {subject,account,calls}=make({barrier:'fail'}),beforeRows=clone(account.rechargeHistory),beforeAudits=clone(subject.auditLogs);
  await subject.saveRecharge();
  same(account.rechargeHistory,beforeRows,'failed recharge row rollback');
  same(subject.auditLogs,beforeAudits,'failed recharge audit rollback');
  eq(subject.showRechargeModal,true,'failed recharge keeps modal open');
  eq(calls.persist,1,'failed recharge persists rollback truth once');
  ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed recharge explains cloud failure');
}

// Unrelated concurrent history appended while ACK is pending is authoritative and survives rollback.
{
  const {subject,account,calls,gate}=make(),task=subject.saveRecharge();
  const concurrent={id:'recharge-concurrent',date:'2026-09-02',currency:'USD',amount:9,note:'concurrent'};
  account.rechargeHistory.push(concurrent);
  gate.reject(new Error('SYNTHETIC_RECHARGE_SAVE_FAILED'));await task;
  eq(account.rechargeHistory.length,1,'failed attempt removed without deleting concurrent history');
  eq(account.rechargeHistory[0],concurrent,'concurrent recharge object preserved');
  eq(calls.persist,1,'concurrent rollback truth persisted');
}

// Same-id account replacement is newer authority; failure never writes the detached old object back into live state.
{
  const {subject,client,account,gate}=make(),task=subject.saveRecharge(),replacement={id:'acct-1',rechargeHistory:[{id:'authoritative',amount:77,currency:'USD'}]};
  client.fbAccounts=[replacement];
  gate.reject(new Error('SYNTHETIC_RECHARGE_SAVE_FAILED'));await task;
  eq(client.fbAccounts[0],replacement,'replacement account remains authoritative');
  same(replacement.rechargeHistory,[{id:'authoritative',amount:77,currency:'USD'}],'replacement history untouched');
  ok(account.rechargeHistory.some(row=>String(row.id).startsWith('recharge-')),'detached attempted object is not used to overwrite replacement authority');
}

// A new form edit while the original recharge is pending must not be closed by the older success callback.
{
  const {subject,gate}=make(),task=subject.saveRecharge();
  subject.rechargeForm.note='new-user-edit';
  gate.resolve(true);await task;
  eq(subject.showRechargeModal,true,'new form edit keeps modal open after older ACK');
  eq(subject.rechargeForm.note,'new-user-edit','new form edit preserved');
}

// Missing durability service fails closed after local rollback with no legacy/cloud write.
{
  const {subject,account,calls}=make();delete subject.persistRechargeBarrier;
  const beforeRows=clone(account.rechargeHistory),beforeAudits=clone(subject.auditLogs),result=subject.saveRecharge();
  eq(result,undefined,'missing barrier returns synchronously');
  same(account.rechargeHistory,beforeRows,'missing barrier leaves recharge history unchanged');
  same(subject.auditLogs,beforeAudits,'missing barrier leaves audit truth unchanged');
  eq(calls.persist,0,'missing barrier sends no legacy persist');
  eq(subject.showRechargeModal,true,'missing barrier keeps modal open');
  ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier notice');
}

// Existing validation and month-lock guards still deny before durable mutation.
for(const amount of ['0','-1','not-a-number','Infinity']){
  const {subject,account,calls}=make({amount}),result=subject.saveRecharge();
  eq(result,undefined,`invalid amount ${amount} synchronous denial`);
  eq(account.rechargeHistory.length,0,`invalid amount ${amount} no history`);
  eq(calls.barrier,0,`invalid amount ${amount} no barrier`);
  eq(calls.persist,0,`invalid amount ${amount} no persist`);
  eq(calls.audit,0,`invalid amount ${amount} no audit`);
}
{
  const {subject,account,calls}=make({date:'2026-02-30'});subject.saveRecharge();
  eq(account.rechargeHistory.length,0,'invalid date no history');eq(calls.barrier,0,'invalid date no barrier');
}
{
  const {subject,account,calls}=make({locked:true});subject.saveRecharge();
  eq(account.rechargeHistory.length,0,'locked month no history');eq(calls.barrier,0,'locked month no barrier');
}

// Historical missing-account behavior remains harmless and closes the stale modal without a write.
{
  const {subject,calls}=make({accountExists:false}),result=subject.saveRecharge();
  eq(result,undefined,'missing account remains synchronous');eq(subject.showRechargeModal,false,'missing account closes modal');eq(calls.barrier,0,'missing account no barrier');eq(calls.persist,0,'missing account no persist');
}

console.log('BUSINESS_RECHARGE_PERSISTENCE_ACK_OK: authority=final-app+shared-flushSave-barrier; recharge=validation+month-lock+success-after-ACK; failure=attempt-history+audit-rollback+rollback-persisted; concurrency=unrelated-history+same-id-account+form/modal-authority-preserved; missing-barrier=fail-closed');
