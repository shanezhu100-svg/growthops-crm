import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const adapter=fs.readFileSync(path.join(root,'dist','cloud-adapter.js'),'utf8');
if(!adapter.includes('vm.persistDeleteAlertBarrier=()=>flushSave();'))throw new Error('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: adapter deleteAlert barrier is not shared flushSave');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: ${name} not found`);
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
  throw new Error(`BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

const source=extractMethod('deleteAlert');
for(const marker of ['persistDeleteAlertBarrier','this.standaloneAlerts=this.standaloneAlerts.filter','this.dismissedAlerts.unshift',"this.logAudit('删除独立提醒'", "this.logAudit('忽略到期提醒'"]){
  if(!source.includes(marker))throw new Error(`BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: shipped deleteAlert missing ${marker}`);
}
const compiled=vm.runInNewContext(`({${source}})`,{JSON,Set,String,Array,Promise,Error,Date,Number,Object,Math},{timeout:1000});
const deleteAlert=compiled.deleteAlert;
if(typeof deleteAlert!=='function')throw new Error('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: deleteAlert not executable');

const fail=m=>{throw new Error('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_FAILED: '+m)};
const eq=(a,b,m)=>{if(JSON.stringify(a)!==JSON.stringify(b))fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
const ok=(v,m)=>{if(!v)fail(m)};
function deferred(){let resolve,reject;const promise=new Promise((res,rej)=>{resolve=res;reject=rej});return{promise,resolve,reject}}

function makeState({standaloneAlerts=[],dismissedAlerts=[],barrierMode='deferred'}={}){
  const notices=[],confirmations=[];let persistCount=0,barrierCount=0;
  const gate=deferred();
  const ctx={
    standaloneAlerts,
    dismissedAlerts,
    auditLogs:[],
    askConfirm(config,action){confirmations.push({config,action});return true},
    persist(){persistCount+=1;return true},
    logAudit(action,detail){const row={action,detail,seq:`audit-${ctx.auditLogs.length+1}`};ctx.auditLogs.push(row);return row},
    notify(...args){notices.push(args.map(String))},
    alertTypeName(key){return String(key||'提醒')},
    alertIgnoreFollowupText(){return '后续阶段仍按规则提醒。'},
    alertDismissKey(item){return `K-${item.id}`},
  };
  if(barrierMode!=='missing')ctx.persistDeleteAlertBarrier=()=>{barrierCount+=1;if(barrierMode==='throw')throw new Error('sync-offline');if(barrierMode==='resolve')return Promise.resolve(true);if(barrierMode==='reject')return Promise.reject(new Error('offline'));return gate.promise};
  return{ctx,notices,confirmations,gate,get persistCount(){return persistCount},get barrierCount(){return barrierCount}};
}

function standaloneItem(id='sa-1'){return{id,isStandalone:true,typeKey:'IP',clientId:'c-1',clientName:'Client One',type:'IP 到期',dueDate:'2026-10-01'}}
function systemItem(id='contract-1'){return{id,isStandalone:false,typeKey:'CONTRACT',clientId:'c-1',clientName:'Client One',type:'合同到期',dueDate:'2026-10-01',reminderIndex:2}}

// Standalone deletion mutates tentatively, suppresses legacy persistence and success UI,
// then exposes success only after the shared cloud ACK.
{
  const target=standaloneItem(),other={id:'sa-2',clientName:'Other'};
  const state=makeState({standaloneAlerts:[target,other]});
  deleteAlert.call(state.ctx,target);
  eq(state.confirmations.length,1,'standalone delete must preserve confirmation');
  const pending=state.confirmations[0].action();
  eq(state.ctx.standaloneAlerts,[other],'standalone target tentatively removed');
  eq(state.persistCount,0,'standalone legacy persist suppressed before ACK');
  eq(state.barrierCount,1,'standalone exactly one durable barrier');
  eq(state.notices.length,0,'standalone success notice held before ACK');
  eq(state.ctx.auditLogs.length,1,'standalone audit tentatively recorded');
  state.gate.resolve(true);await pending;
  eq(state.ctx.standaloneAlerts,[other],'standalone delete retained after ACK');
  eq(state.notices.length,1,'standalone success notice emitted after ACK');
}

// Failed standalone delete restores only the attempt-owned row/audit, at its semantic
// position, while preserving unrelated concurrent rows and audits.
{
  const before={id:'sa-before'},target=standaloneItem(),after={id:'sa-after'};
  const state=makeState({standaloneAlerts:[before,target,after]});
  deleteAlert.call(state.ctx,target);const pending=state.confirmations[0].action();
  const concurrent={id:'sa-newer'};state.ctx.standaloneAlerts.unshift(concurrent);
  const concurrentAudit={action:'并发审计'};state.ctx.auditLogs.unshift(concurrentAudit);
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.standaloneAlerts,[concurrent,before,target,after],'failed delete restores target without overwriting concurrent order');
  eq(state.ctx.auditLogs,[concurrentAudit],'failed delete removes only attempt audit');
  eq(state.persistCount,1,'failed delete persists rollback truth once');
  ok(state.notices.at(-1)?.[0].includes('云端保存失败'),'failed delete emits failure notice');
}

// Same-ID replacement and whole-array replacement are newer authority and must win.
{
  const target=standaloneItem(),state=makeState({standaloneAlerts:[target]});
  deleteAlert.call(state.ctx,target);const pending=state.confirmations[0].action();
  const replacement={...target,clientName:'Newer Authority'};state.ctx.standaloneAlerts.unshift(replacement);
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.standaloneAlerts,[replacement],'same-id replacement survives failed delete');
}
{
  const target=standaloneItem(),state=makeState({standaloneAlerts:[target]});
  deleteAlert.call(state.ctx,target);const pending=state.confirmations[0].action();
  const replacementArray=[{id:'whole-array-authority'}];state.ctx.standaloneAlerts=replacementArray;
  state.gate.reject(new Error('offline'));await pending;
  ok(state.ctx.standaloneAlerts===replacementArray,'whole-array concurrent authority preserved');
  eq(state.ctx.standaloneAlerts,replacementArray,'failed delete does not inject stale row into replacement array');
}

// System reminder ignore follows the same ACK boundary; failure removes only the
// attempt-owned dismissal and audit while preserving unrelated concurrent state.
{
  const item=systemItem(),state=makeState({dismissedAlerts:[]});
  deleteAlert.call(state.ctx,item);eq(state.confirmations.length,1,'system ignore preserves confirmation');
  const pending=state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts.length,1,'system dismissal tentatively added');
  eq(state.ctx.dismissedAlerts[0].key,'K-contract-1','system dismissal key preserved');
  eq(state.persistCount,0,'system ignore legacy persist suppressed');
  eq(state.barrierCount,1,'system ignore exactly one durable barrier');
  eq(state.notices.length,0,'system ignore success notice held before ACK');
  state.gate.resolve(true);await pending;
  eq(state.notices.length,1,'system ignore success notice emitted after ACK');
}
{
  const existing={key:'K-existing',id:'existing'},item=systemItem(),state=makeState({dismissedAlerts:[existing]});
  deleteAlert.call(state.ctx,item);const pending=state.confirmations[0].action();
  const attempt=state.ctx.dismissedAlerts[0],concurrent={key:'K-newer',id:'newer'};state.ctx.dismissedAlerts.unshift(concurrent);
  const concurrentAudit={action:'并发审计'};state.ctx.auditLogs.unshift(concurrentAudit);
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.dismissedAlerts,[concurrent,existing],'failed ignore removes only attempt dismissal');
  ok(!state.ctx.dismissedAlerts.includes(attempt),'attempt dismissal removed by identity');
  eq(state.ctx.auditLogs,[concurrentAudit],'failed ignore removes only attempt audit');
  eq(state.persistCount,1,'failed ignore persists rollback truth once');
}

// If the attempt row is replaced under the same key, the replacement is newer authority.
{
  const item=systemItem(),state=makeState({dismissedAlerts:[]});
  deleteAlert.call(state.ctx,item);const pending=state.confirmations[0].action();
  const attempt=state.ctx.dismissedAlerts[0],replacement={...attempt,ignoredAt:'newer-authority'};state.ctx.dismissedAlerts[0]=replacement;
  state.gate.reject(new Error('offline'));await pending;
  eq(state.ctx.dismissedAlerts,[replacement],'same-key replacement survives failed ignore');
}

// Existing dismissal keeps the legacy no-duplicate state semantics but still receives
// the durable ACK for its persist/audit/success operation.
{
  const item=systemItem(),existing={key:'K-contract-1',id:item.id},state=makeState({dismissedAlerts:[existing],barrierMode:'resolve'});
  deleteAlert.call(state.ctx,item);await state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[existing],'duplicate dismissal not re-added');
  eq(state.barrierCount,1,'duplicate dismissal still ACKs reviewed persist operation');
  eq(state.persistCount,0,'duplicate dismissal legacy persist collapsed into ACK');
  eq(state.ctx.auditLogs.length,1,'duplicate dismissal preserves legacy audit semantics');
  eq(state.notices.length,1,'duplicate dismissal preserves success notice after ACK');
}

// Missing barrier fails closed with synchronous rollback and zero legacy persist.
{
  const target=standaloneItem(),state=makeState({standaloneAlerts:[target],barrierMode:'missing'});
  deleteAlert.call(state.ctx,target);state.confirmations[0].action();
  eq(state.ctx.standaloneAlerts,[target],'missing barrier rolls standalone delete back');
  eq(state.ctx.auditLogs.length,0,'missing barrier removes attempt audit');
  eq(state.persistCount,0,'missing barrier performs zero legacy persist');
  ok(state.notices.at(-1)?.[0].includes('持久化服务不可用'),'missing barrier emits fail-closed notice');
}

// A synchronously throwing barrier is a failed ACK: rollback and persist rollback truth once.
{
  const item=systemItem(),state=makeState({dismissedAlerts:[],barrierMode:'throw'});
  deleteAlert.call(state.ctx,item);state.confirmations[0].action();
  eq(state.ctx.dismissedAlerts,[],'sync barrier throw rolls dismissal back');
  eq(state.ctx.auditLogs.length,0,'sync barrier throw removes attempt audit');
  eq(state.persistCount,1,'sync barrier throw persists rollback truth once');
  ok(state.notices.at(-1)?.[0].includes('云端保存失败'),'sync barrier throw emits failure notice');
}

// Auto recharge reminders are informational/system-owned and remain a no-persist path.
{
  const state=makeState({barrierMode:'resolve'}),item={id:'recharge-1',typeKey:'AD_RECHARGE',clientName:'Client One'};
  deleteAlert.call(state.ctx,item);
  eq(state.confirmations.length,0,'ad recharge path does not ask destructive confirmation');
  eq(state.barrierCount,0,'ad recharge path does not call delete barrier');
  eq(state.persistCount,0,'ad recharge path remains non-persisting');
  eq(state.ctx.auditLogs.length,0,'ad recharge path remains non-auditing');
  eq(state.notices.length,1,'ad recharge explanatory notice preserved');
}
{
  const state=makeState({barrierMode:'resolve'});deleteAlert.call(state.ctx,null);
  eq(state.confirmations.length,0,'null alert is a no-op');eq(state.barrierCount,0,'null alert has no barrier');eq(state.persistCount,0,'null alert has no persist');
}

console.log('BUSINESS_DELETE_ALERT_PERSISTENCE_ACK_OK: standalone-delete+system-dismiss=single-shared-cloud-ACK-before-success; failure=operation-owned-row+dismissal+audit-rollback+rollback-persisted; concurrency=unrelated+same-id+same-key+whole-array-authority-preserved; missing-barrier=fail-closed; ad-recharge=no-persist-unchanged');