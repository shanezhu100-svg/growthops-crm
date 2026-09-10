import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd(),appDir=path.join(root,'dist','app'),adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort(),bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const adapter=fs.readFileSync(adapterPath,'utf8');
if(!adapter.includes('vm.persistRenewalBarrier=()=>flushSave();'))throw new Error('BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: renewal barrier is not wired to shared flushSave');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m'),match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('saveRenewal')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise,Error},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: final saveRenewal not executable: ${error.message}`)}

const clone=v=>JSON.parse(JSON.stringify(v));
const fail=m=>{throw new Error('BUSINESS_RENEWAL_PERSISTENCE_ACK_FAILED: '+m)};
const ok=(v,m)=>{if(!v)fail(m)};
const eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
const same=(a,b,m)=>{if(JSON.stringify(a)!==JSON.stringify(b))fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
function deferred(){let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return{promise,resolve,reject}}

function makeContract({barrier='deferred',newDue='2026-12-31',autoBills=true}={}){
  const gate=deferred(),calls={barrier:0,persist:0,notify:[],audit:0,auto:0},client={id:'client-1',name:'Client One',endDate:'2026-10-01',renewalHistory:[],networkEnvironments:[]},target={id:'contract-client-1',isStandalone:false,typeKey:'CONTRACT',dueDate:'2026-10-01',clientId:'client-1',clientName:'Client One',type:'合同'},dismissed={key:'contract-client-1|2026-10-01|3',id:'contract-client-1',dueDate:'2026-10-01',typeKey:'CONTRACT',clientId:'client-1'};
  const subject={...methods,clients:[client],standaloneAlerts:[],financeReceivables:[],dismissedAlerts:[dismissed],renewalTarget:target,renewalForm:{newDueDate:newDue,note:'renewed'},showRenewalModal:true,auditLogs:[{id:'audit-existing',action:'EXISTING'}],localDateKey(){return'2026-09-09'},syncLegacyNetworkFields(){},ensureAutomaticReceivables(){calls.auto+=1;if(!autoBills)return 0;const row={id:'ar-renewal',clientId:'client-1',settlementMonth:'2026-11',amount:100,billSource:'AUTO_SERVICE_FEE'};this.financeReceivables.unshift(row);this.persist();this.logAudit('自动生成应收账单','1 条');return 1},persist(){calls.persist+=1},persistRenewalBarrier(){calls.barrier+=1;if(barrier==='ok')return Promise.resolve(true);if(barrier==='fail')return Promise.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));return gate.promise},logAudit(action,targetText){calls.audit+=1;const row={id:`audit-${calls.audit}`,action:String(action),target:String(targetText)};this.auditLogs.push(row);return row},notify(message){calls.notify.push(String(message))},alertTypeName(k){return k}};
  return{subject,client,target,dismissed,calls,gate};
}

function makeStandalone({barrier='deferred'}={}){
  const gate=deferred(),calls={barrier:0,persist:0,notify:[],audit:0},alert={id:'sa-1',dueDate:'2026-10-01'},target={id:'sa-1',isStandalone:true,typeKey:'IP',dueDate:'2026-10-01',clientName:'Manual',type:'IP'},dismissed={key:'sa-1|2026-10-01|3',id:'sa-1',dueDate:'2026-10-01',typeKey:'IP'};
  const subject={...methods,clients:[],standaloneAlerts:[alert],financeReceivables:[],dismissedAlerts:[dismissed],renewalTarget:target,renewalForm:{newDueDate:'2026-12-31',note:'renewed'},showRenewalModal:true,auditLogs:[{id:'audit-existing'}],localDateKey(){return'2026-09-09'},persist(){calls.persist+=1},persistRenewalBarrier(){calls.barrier+=1;if(barrier==='ok')return Promise.resolve(true);if(barrier==='fail')return Promise.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));return gate.promise},logAudit(action,targetText){calls.audit+=1;const row={id:`audit-${calls.audit}`,action:String(action),target:String(targetText)};this.auditLogs.push(row);return row},notify(message){calls.notify.push(String(message))},alertTypeName(k){return k},ensureAutomaticReceivables(){throw new Error('standalone must not auto bill')},syncLegacyNetworkFields(){}};
  return{subject,alert,target,dismissed,calls,gate};
}

function makeIp({barrier='deferred',legacy=false}={}){
  const gate=deferred(),calls={barrier:0,persist:0,notify:[],audit:0,sync:0},env={id:'net-1',ipDueDate:'2026-10-01',ipEnvironment:'Env A'},client={id:'client-1',name:'Client One',ipDueDate:'2026-10-01',ipEnvironment:'Env A',networkEnvironments:legacy?[]:[env]},target={id:legacy?'ip-client-1-legacy':'ip-client-1-net-1',isStandalone:false,typeKey:'IP',networkId:legacy?'':'net-1',dueDate:'2026-10-01',clientId:'client-1',clientName:'Client One',type:'IP'};
  const subject={...methods,clients:[client],standaloneAlerts:[],financeReceivables:[],dismissedAlerts:[{key:'ip-key',id:target.id,dueDate:target.dueDate,typeKey:'IP',clientId:'client-1',networkId:target.networkId}],renewalTarget:target,renewalForm:{newDueDate:'2026-12-31',note:'renewed'},showRenewalModal:true,auditLogs:[{id:'audit-existing'}],localDateKey(){return'2026-09-09'},syncLegacyNetworkFields(c){calls.sync+=1;if(!legacy&&c.networkEnvironments[0]){c.ipDueDate=c.networkEnvironments[0].ipDueDate;c.ipEnvironment=c.networkEnvironments[0].ipEnvironment}},ensureAutomaticReceivables(){return 0},persist(){calls.persist+=1},persistRenewalBarrier(){calls.barrier+=1;if(barrier==='ok')return Promise.resolve(true);if(barrier==='fail')return Promise.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));return gate.promise},logAudit(action,targetText){calls.audit+=1;const row={id:`audit-${calls.audit}`,action:String(action),target:String(targetText)};this.auditLogs.push(row);return row},notify(message){calls.notify.push(String(message))},alertTypeName(k){return k}};
  return{subject,client,env,target,calls,gate};
}

// Contract renewal and automatic receivable generation remain tentative until one shared ACK.
{
  const {subject,client,target,calls,gate}=makeContract(),task=subject.saveRenewal();
  ok(task&&typeof task.then==='function','contract renewal returns ACK promise');
  eq(calls.barrier,1,'contract renewal crosses barrier once');
  eq(calls.persist,0,'helper+outer legacy persists suppressed');
  eq(client.endDate,'2026-12-31','contract date tentatively updated');
  eq(client.renewalHistory.length,1,'renewal history tentatively added');
  eq(subject.financeReceivables.length,1,'automatic receivable tentatively added');
  eq(subject.dismissedAlerts.length,0,'old dismissal tentatively removed');
  eq(subject.showRenewalModal,true,'renewal modal stays open before ACK');
  eq(subject.renewalTarget,target,'renewal target stays selected before ACK');
  eq(calls.notify.length,0,'success notice held before ACK');
  gate.resolve(true);await task;
  eq(subject.showRenewalModal,false,'contract modal closes after ACK');
  eq(subject.renewalTarget,null,'renewal target clears after ACK');
  ok(calls.notify.some(m=>m.includes('续费已保存')),'contract success notice emitted after ACK');
  eq(calls.audit,2,'contract renewal keeps helper+renewal audit truth');
}

// Failed contract ACK restores date/history/dismissal and only attempt-owned automatic receivable/audits.
{
  const {subject,client,target,calls}=makeContract({barrier:'fail'}),beforeAudits=clone(subject.auditLogs),beforeDismissed=clone(subject.dismissedAlerts);
  await subject.saveRenewal();
  eq(client.endDate,'2026-10-01','failed contract date rollback');
  eq(client.renewalHistory.length,0,'failed contract history rollback');
  eq(subject.financeReceivables.length,0,'failed contract auto receivable rollback');
  same(subject.dismissedAlerts,beforeDismissed,'failed contract dismissal rollback');
  same(subject.auditLogs,beforeAudits,'failed contract attempt audits rollback');
  eq(subject.showRenewalModal,true,'failed contract keeps modal open');
  eq(subject.renewalTarget,target,'failed contract keeps target');
  eq(calls.persist,1,'failed contract persists rollback truth once');
  ok(calls.notify.some(m=>m.includes('云端保存失败')),'failed contract explains cloud failure');
}

// Concurrent finance/history/audit edits win while the failed attempt itself is removed.
{
  const {subject,client,calls,gate}=makeContract(),task=subject.saveRenewal(),concurrentHistory={date:'2026-09-09',newEndDate:'2027-01-31',note:'concurrent'},concurrentReceivable={id:'ar-concurrent',clientId:'client-1',amount:77},concurrentAudit={id:'audit-concurrent'};
  client.endDate='2027-01-31';client.renewalHistory.push(concurrentHistory);subject.financeReceivables.push(concurrentReceivable);subject.auditLogs.push(concurrentAudit);subject.dismissedAlerts.push({key:'other',id:'other'});
  gate.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));await task;
  eq(client.endDate,'2027-01-31','concurrent contract date preserved');
  eq(client.renewalHistory.length,1,'attempt history removed without concurrent history');eq(client.renewalHistory[0],concurrentHistory,'concurrent history object preserved');
  eq(subject.financeReceivables.length,1,'attempt receivable removed without concurrent receivable');eq(subject.financeReceivables[0],concurrentReceivable,'concurrent receivable preserved');
  ok(subject.auditLogs.includes(concurrentAudit),'concurrent audit preserved');ok(subject.dismissedAlerts.some(x=>x.id==='other'),'concurrent dismissal preserved');
  eq(calls.persist,1,'concurrent rollback truth persisted');
}

// Same-id client replacement is newer authority and is never overwritten by an older failed renewal.
{
  const {subject,client,gate}=makeContract(),task=subject.saveRenewal(),replacement={id:'client-1',name:'Replacement',endDate:'2028-01-01',renewalHistory:[{note:'authoritative'}],networkEnvironments:[]};
  subject.clients=[replacement];gate.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));await task;
  eq(subject.clients[0],replacement,'replacement client remains authoritative');eq(replacement.endDate,'2028-01-01','replacement date untouched');eq(replacement.renewalHistory.length,1,'replacement history untouched');
  eq(client.endDate,'2026-12-31','detached attempted object is not written back into live replacement');
}

// Standalone renewal is also ACK-gated and restores exact reminder/dismissal state on failure.
{
  const {subject,alert,target,calls,gate}=makeStandalone(),task=subject.saveRenewal();
  eq(alert.dueDate,'2026-12-31','standalone tentative due date');eq(subject.dismissedAlerts.length,0,'standalone dismissal tentative removal');eq(subject.showRenewalModal,true,'standalone modal held');
  gate.resolve(true);await task;eq(subject.showRenewalModal,false,'standalone modal closes after ACK');eq(subject.renewalTarget,null,'standalone target clears after ACK');ok(calls.notify.some(m=>m.includes('续费已保存')),'standalone success after ACK');
}
{
  const {subject,alert,target,calls}=makeStandalone({barrier:'fail'}),beforeDismissed=clone(subject.dismissedAlerts);await subject.saveRenewal();
  eq(alert.dueDate,'2026-10-01','standalone failure restores due date');same(subject.dismissedAlerts,beforeDismissed,'standalone failure restores dismissal');eq(subject.renewalTarget,target,'standalone failure keeps target');eq(calls.persist,1,'standalone rollback persisted');
}

// Modern IP renewal restores both exact environment and synchronized legacy fields; newer field edits win.
{
  const {subject,client,env,calls}=makeIp({barrier:'fail'});await subject.saveRenewal();
  eq(env.ipDueDate,'2026-10-01','modern IP env date rollback');eq(client.ipDueDate,'2026-10-01','modern IP synced root date rollback');eq(calls.persist,1,'modern IP rollback persisted');
}
{
  const {subject,client,env,gate}=makeIp(),task=subject.saveRenewal();env.ipDueDate='2027-02-01';client.ipDueDate='2027-02-01';gate.reject(new Error('SYNTHETIC_RENEWAL_SAVE_FAILED'));await task;
  eq(env.ipDueDate,'2027-02-01','concurrent env date preserved');eq(client.ipDueDate,'2027-02-01','concurrent synchronized root date preserved');
}

// Legacy root IP renewal remains supported and durable.
{
  const {subject,client,gate,calls}=makeIp({legacy:true}),task=subject.saveRenewal();eq(client.ipDueDate,'2026-12-31','legacy IP tentative date');gate.resolve(true);await task;eq(client.ipDueDate,'2026-12-31','legacy IP date survives ACK');eq(calls.barrier,1,'legacy IP barrier once');
}

// Missing durability service fails closed with full local rollback and zero legacy write.
{
  const {subject,client,target,calls}=makeContract();delete subject.persistRenewalBarrier;const before=clone({client,dismissed:subject.dismissedAlerts,receivables:subject.financeReceivables,audits:subject.auditLogs}),result=subject.saveRenewal();
  eq(result,undefined,'missing barrier returns synchronously');eq(client.endDate,before.client.endDate,'missing barrier restores client');same(subject.dismissedAlerts,before.dismissed,'missing barrier restores dismissals');same(subject.financeReceivables,before.receivables,'missing barrier restores receivables');same(subject.auditLogs,before.audits,'missing barrier restores audits');eq(subject.renewalTarget,target,'missing barrier keeps target');eq(calls.persist,0,'missing barrier zero legacy persist');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier notice');
}

// Existing date and stale-target guards still deny before the durability barrier.
{
  const {subject,client,calls}=makeContract({newDue:'2026-02-30'}),result=subject.saveRenewal();eq(result,undefined,'invalid date denied synchronously');eq(client.endDate,'2026-10-01','invalid date no mutation');eq(calls.barrier,0,'invalid date no barrier');eq(calls.persist,0,'invalid date no persist');eq(calls.audit,0,'invalid date no audit');
}
{
  const {subject,client,calls}=makeContract();client.endDate='2026-11-01';const result=subject.saveRenewal();eq(result,undefined,'stale contract denied synchronously');eq(client.endDate,'2026-11-01','stale contract preserves authoritative date');eq(calls.barrier,0,'stale contract no barrier');eq(calls.persist,0,'stale contract no persist');eq(calls.audit,0,'stale contract no audit');
}

console.log('BUSINESS_RENEWAL_PERSISTENCE_ACK_OK: authority=final-app+shared-flushSave-barrier; standalone+contract+ip=success-after-ACK; contract-auto-receivables=helper-persists-collapsed; failure=due-date+history+dismissed+attempt-receivable+audit rollback+rollback-persisted; concurrency=client/env/finance/history/audit authority preserved; missing-barrier=fail-closed');
