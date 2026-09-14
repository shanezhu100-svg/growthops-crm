import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const adapter=fs.readFileSync(path.join(root,'dist','cloud-adapter.js'),'utf8');
if(!adapter.includes('vm.persistRestoreDismissedAlertsBarrier=()=>flushSave();'))throw new Error('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: adapter restore barrier is not shared flushSave');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

const source=extractMethod('restoreDismissedAlerts');
for(const marker of ['persistRestoreDismissedAlertsBarrier','initialRestoreKeys=new Set','initialRestoreKeys].filter(key=>liveActiveKeys.has(key))',"this.logAudit('恢复已忽略提醒'",'this.contractDueReminderStage(c,c.endDate)']){
  if(!source.includes(marker))throw new Error(`BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: shipped restoreDismissedAlerts missing ${marker}`);
}
const compiled=vm.runInNewContext(`({${source}})`,{JSON,Set,String,Array,Promise,Error,Date,Number,Object,Math},{timeout:1000});
const restoreDismissedAlerts=compiled.restoreDismissedAlerts;
if(typeof restoreDismissedAlerts!=='function')throw new Error('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: restoreDismissedAlerts not executable');

const fail=m=>{throw new Error('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FAILED: '+m)};
const eq=(a,b,m)=>{if(JSON.stringify(a)!==JSON.stringify(b))fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
const ok=(v,m)=>{if(!v)fail(m)};
function deferred(){let resolve,reject;const promise=new Promise((res,rej)=>{resolve=res;reject=rej});return{promise,resolve,reject}}

const due='2026-09-10';
const contractKey=`CONTRACT-c1|${due}|2`;
const ipKey=`IP-c1-ip1|${due}|2`;
const receivableKey=`RECEIVABLE-r1|${due}|2`;
function dismissal(key,id=key){return{key,id,clientId:'c1',dueDate:due}}
function makeState({dismissedAlerts=[dismissal(contractKey)],barrierMode='deferred'}={}){
  const notices=[],confirmations=[];let persistCount=0,barrierCount=0;
  const gate=deferred();
  const client={id:'c1',endDate:due,archived:false,networkEnvironments:[{id:'ip1',ipDueDate:due}]};
  const ctx={
    clients:[client],financeReceivables:[{id:'r1',dueDate:due,unpaid:100}],dismissedAlerts,auditLogs:[],
    contractDueReminderStage(c,date){return date?{reminderIndex:2}:null},
    autoDueReminderStage(date){return date?{reminderIndex:2}:null},
    financeReceivableUnpaid(row){return Number(row.unpaid||0)},
    askConfirm(config,action){confirmations.push({config,action});return true},
    persist(){persistCount+=1;return true},
    logAudit(action,detail){const row={action,detail,seq:`audit-${ctx.auditLogs.length+1}`};ctx.auditLogs.push(row);return row},
    notify(...args){notices.push(args.map(String))},
  };
  if(barrierMode!=='missing')ctx.persistRestoreDismissedAlertsBarrier=()=>{barrierCount+=1;if(barrierMode==='throw')throw new Error('sync-offline');if(barrierMode==='resolve')return Promise.resolve(true);if(barrierMode==='reject')return Promise.reject(new Error('offline'));return gate.promise};
  return{ctx,client,notices,confirmations,gate,get persistCount(){return persistCount},get barrierCount(){return barrierCount}};
}

// All currently active dismissed rows are removed tentatively, but success UI waits
// until the shared cloud queue acknowledges both state and audit truth.
{
  const unrelated=dismissal('UNRELATED','keep');
  const state=makeState({dismissedAlerts:[dismissal(contractKey,'contract'),dismissal(ipKey,'ip'),dismissal(receivableKey,'receivable'),unrelated]});
  restoreDismissedAlerts.call(state.ctx);
  eq(state.confirmations.length,1,'restore must preserve confirmation');
  const pending=state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[unrelated],'active dismissals tentatively removed');
  eq(state.persistCount,0,'legacy persist suppressed before ACK');
  eq(state.barrierCount,1,'exactly one durable restore barrier');
  eq(state.ctx.auditLogs.length,1,'restore audit tentatively recorded');
  eq(state.notices.length,0,'success notice held before ACK');
  state.gate.resolve(true);await pending;
  eq(state.ctx.dismissedAlerts,[unrelated],'restored dismissals remain removed after ACK');
  eq(state.notices.length,1,'success notice emitted after ACK');
  ok(state.notices[0][0].includes('3 条'),'success notice reports actual restored count');
}

// A failed ACK restores only rows and audit owned by this attempt while preserving
// unrelated rows/audits added concurrently and the semantic row position.
{
  const before=dismissal('UNRELATED-BEFORE','before'),target=dismissal(contractKey,'target'),after=dismissal('UNRELATED-AFTER','after');
  const state=makeState({dismissedAlerts:[before,target,after]});
  restoreDismissedAlerts.call(state.ctx);const pending=state.confirmations[0].action();
  const concurrent=dismissal('UNRELATED-NEW','newer');state.ctx.dismissedAlerts.unshift(concurrent);
  const concurrentAudit={action:'并发审计'};state.ctx.auditLogs.unshift(concurrentAudit);
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.dismissedAlerts,[concurrent,before,target,after],'failed restore rolls target back without losing concurrent rows');
  eq(state.ctx.auditLogs,[concurrentAudit],'failed restore removes only attempt audit');
  eq(state.persistCount,1,'failed restore persists rollback truth once');
  ok(state.notices.at(-1)?.[0].includes('云端保存失败'),'failed restore emits failure notice');
}

// A newer same-key replacement wins over the attempt-owned old dismissal on failure.
{
  const target=dismissal(contractKey,'old'),state=makeState({dismissedAlerts:[target]});
  restoreDismissedAlerts.call(state.ctx);const pending=state.confirmations[0].action();
  const replacement={...target,id:'newer',dismissedAt:'newer-authority'};state.ctx.dismissedAlerts.unshift(replacement);
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.dismissedAlerts,[replacement],'same-key replacement survives failed restore');
}

// Whole-array replacement is newer state authority; rollback must not inject stale rows.
{
  const target=dismissal(contractKey,'old'),state=makeState({dismissedAlerts:[target]});
  restoreDismissedAlerts.call(state.ctx);const pending=state.confirmations[0].action();
  const replacementArray=[dismissal('WHOLE-ARRAY-AUTHORITY','newer')];state.ctx.dismissedAlerts=replacementArray;
  state.gate.reject(new Error('offline'));await pending;
  ok(state.ctx.dismissedAlerts===replacementArray,'whole-array authority identity preserved');
  eq(state.ctx.dismissedAlerts,replacementArray,'failed restore does not inject stale row into replacement array');
  eq(state.persistCount,1,'whole-array failure persists current rollback truth once');
}

// Missing durable service fails closed before tentative mutation/audit and performs
// zero legacy persistence calls.
{
  const target=dismissal(contractKey,'target'),state=makeState({dismissedAlerts:[target],barrierMode:'missing'});
  restoreDismissedAlerts.call(state.ctx);state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[target],'missing barrier leaves dismissal unchanged');
  eq(state.ctx.auditLogs.length,0,'missing barrier records no audit');
  eq(state.persistCount,0,'missing barrier performs zero legacy persist');
  eq(state.barrierCount,0,'missing barrier performs zero durable calls');
  ok(state.notices.at(-1)?.[0].includes('持久化服务不可用'),'missing barrier emits fail-closed notice');
}

// A synchronous cloud failure is still an ACK failure: rollback and persist that
// rollback truth once through the legacy queue.
{
  const target=dismissal(contractKey,'target'),state=makeState({dismissedAlerts:[target],barrierMode:'throw'});
  restoreDismissedAlerts.call(state.ctx);state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[target],'sync barrier throw restores dismissal');
  eq(state.ctx.auditLogs.length,0,'sync barrier throw removes attempt audit');
  eq(state.persistCount,1,'sync barrier throw persists rollback truth once');
  ok(state.notices.at(-1)?.[0].includes('云端保存失败'),'sync barrier throw emits failure notice');
}

// Existing confirmation-time integrity remains authoritative: if the reminder goes
// inactive before confirmation, there is no mutation, audit, persist, or ACK.
{
  const target=dismissal(contractKey,'target'),state=makeState({dismissedAlerts:[target],barrierMode:'resolve'});
  restoreDismissedAlerts.call(state.ctx);eq(state.confirmations.length,1,'stale-state case opens confirmation');
  state.client.archived=true;
  state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[target],'inactive-at-confirm dismissal remains');
  eq(state.ctx.auditLogs.length,0,'inactive-at-confirm no audit');
  eq(state.persistCount,0,'inactive-at-confirm no persist');
  eq(state.barrierCount,0,'inactive-at-confirm no barrier');
  ok(state.notices.at(-1)?.[0].includes('状态已变化'),'inactive-at-confirm notice preserved');
}

console.log('BUSINESS_DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_OK: confirmation-time-integrity=preserved; restore=single-shared-cloud-ACK-before-success; failure=attempt-rows+audit-rollback+rollback-persisted; concurrency=unrelated+same-key+whole-array-authority-preserved; missing-barrier=fail-closed');
