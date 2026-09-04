import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
const defRe=/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/gm;
const defs=[...bundle.matchAll(defRe)];
function extract(name){
  const i=defs.findIndex(m=>m[1]===name);if(i<0||i+1>=defs.length)throw new Error(`BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FAILED: ${name} boundary missing`);
  const start=defs[i].index+defs[i][0].indexOf(name),next=defs[i+1].index+defs[i+1][0].indexOf(defs[i+1][1]);
  return bundle.slice(start,next).replace(/,\s*$/,'').trim();
}
const toggle=vm.runInNewContext(`({${extract('toggleFinanceMonthLock')}})`,{Date,Math,Number,String,Object,Array,JSON,Set},{timeout:1000}).toggleFinanceMonthLock;
const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
if(!adapter.includes('vm.persistFinanceMonthLockBarrier=()=>flushSave();'))throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FAILED: final adapter month-lock barrier missing');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const fail=message=>{throw new Error('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const ok=(value,label)=>{if(!value)fail(label)};

function parseSave(call){
  if(!call)fail('missing save call');
  const body=JSON.parse(call.body||'{}');
  if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);
  return body.args?.p_state;
}

function makeRuntime({locked,behavior='fail-first'}){
  const month='2026-09';
  const calls={fetch:[],notify:[]};
  let confirmAction=null,auditId=0,saveAttempt=0,resolveFirst=null;
  const subject={};
  const existingLock={lockedAt:'2026-09-01T00:00:00.000Z',lockedBy:'Admin',snapshotAt:'2026-09-01T00:00:00.000Z'};
  const existingSnapshot={createdAt:'2026-09-01T00:00:00.000Z',income:123};
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#finance'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const successResponse=()=>({ok:true,status:200,json:async()=>({revision:saveAttempt})});
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});
    saveAttempt+=1;
    if(behavior==='gated-success'&&saveAttempt===1)return new Promise(resolve=>{resolveFirst=()=>resolve(successResponse());});
    if(behavior==='fail-first'&&saveAttempt===1)return {ok:false,status:503,json:async()=>({message:'SYNTHETIC_MONTH_LOCK_SAVE_FAILED'})};
    return successResponse();
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  Object.assign(subject,{
    toggleFinanceMonthLock:toggle,
    currentUser:locked?{id:'admin',name:'Admin',role:'ADMIN',enabled:true}:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},
    financeMonthLocks:locked?{[month]:structuredClone(existingLock)}:{},
    financeMonthSnapshots:locked?{[month]:structuredClone(existingSnapshot)}:{},
    auditLogs:[],backupSnapshots:[],clients:[],
    canManageFinance:()=>true,
    isMonthLocked:key=>Boolean(subject.financeMonthLocks[key]),
    ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},ensureDailyBackup:()=>{},
    runFinanceMonthCheck:()=>({issues:[]}),getFinanceMonthCheck:()=>({issues:[]}),
    buildFinanceMonthSnapshot:()=>({createdAt:'2026-09-03T00:00:00.000Z',income:456}),
    askConfirm:(_config,action)=>{confirmAction=action;},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action,target};subject.auditLogs.push(row);return row;},
    notify:message=>calls.notify.push(String(message)),
    collectBackupPayload:()=>({clients:[],financeMonthLocks:structuredClone(subject.financeMonthLocks),financeMonthSnapshots:structuredClone(subject.financeMonthSnapshots),auditLogs:structuredClone(subject.auditLogs),backupSnapshots:[]}),
  });
  return {subject,calls,month,existingLock,existingSnapshot,getConfirm:()=>confirmAction,resolveFirst:()=>resolveFirst?.()};
}

// Successful lock: local tentative state exists while save is pending, but user-visible
// success and the durable audit do not cross the boundary until the save ACK arrives.
{
  const r=makeRuntime({locked:false,behavior:'gated-success'});
  r.subject.toggleFinanceMonthLock(r.month);
  const confirm=r.getConfirm();ok(typeof confirm==='function','lock confirmation missing');
  const pending=confirm();
  await Promise.resolve();await Promise.resolve();
  eq(r.calls.fetch.length,1,'lock starts exactly one acknowledged save');
  ok(Boolean(r.subject.financeMonthLocks[r.month]),'lock tentative state exists while ACK pending');
  ok(r.subject.auditLogs.some(row=>row.action==='完成财务月结'),'lock tentative audit exists while ACK pending');
  ok(!r.calls.notify.some(message=>message.includes('已完成月结')),'lock success must wait for ACK');
  const saved=parseSave(r.calls.fetch[0]);
  ok(Boolean(saved?.financeMonthLocks?.[r.month]),'lock save payload contains lock state');
  ok(saved?.auditLogs?.some(row=>row.action==='完成财务月结'),'lock save payload contains audit');
  r.resolveFirst();await pending;
  ok(r.calls.notify.some(message=>message.includes('已完成月结')),'lock success emitted after ACK');
}

// Successful unlock has the symmetric ACK boundary.
{
  const r=makeRuntime({locked:true,behavior:'gated-success'});
  r.subject.toggleFinanceMonthLock(r.month);
  const confirm=r.getConfirm();ok(typeof confirm==='function','unlock confirmation missing');
  const pending=confirm();
  await Promise.resolve();await Promise.resolve();
  eq(r.calls.fetch.length,1,'unlock starts exactly one acknowledged save');
  ok(!Object.hasOwn(r.subject.financeMonthLocks,r.month),'unlock tentative state removes lock while ACK pending');
  ok(r.subject.auditLogs.some(row=>row.action==='解除财务月结'),'unlock tentative audit exists while ACK pending');
  ok(!r.calls.notify.some(message=>message.includes('已解锁')),'unlock success must wait for ACK');
  const saved=parseSave(r.calls.fetch[0]);
  ok(!saved?.financeMonthLocks?.[r.month],'unlock save payload removes lock state');
  ok(saved?.auditLogs?.some(row=>row.action==='解除财务月结'),'unlock save payload contains audit');
  r.resolveFirst();await pending;
  ok(r.calls.notify.some(message=>message.includes('已解锁')),'unlock success emitted after ACK');
}

// Failed lock: rollback only this attempt, preserve an unrelated concurrent audit,
// and make the automatic rollback persist incapable of resurrecting the false lock.
{
  const r=makeRuntime({locked:false,behavior:'fail-first'});
  r.subject.toggleFinanceMonthLock(r.month);
  const confirm=r.getConfirm();ok(typeof confirm==='function','failed-lock confirmation missing');
  const pending=confirm();
  const unrelated={id:'audit-unrelated-lock',action:'并发审计',target:'keep'};r.subject.auditLogs.push(unrelated);
  await pending;
  ok(!Object.hasOwn(r.subject.financeMonthLocks,r.month),'failed lock restores unlocked state');
  ok(!Object.hasOwn(r.subject.financeMonthSnapshots,r.month),'failed lock removes tentative snapshot');
  ok(!r.subject.auditLogs.some(row=>row.action==='完成财务月结'),'failed lock removes attempt audit');
  ok(r.subject.auditLogs.includes(unrelated),'failed lock preserves unrelated audit by identity');
  ok(!r.calls.notify.some(message=>message.includes('已完成月结')),'failed lock never emits success');
  ok(r.calls.notify.some(message=>message.includes('月结未完成')&&message.includes('已恢复未锁定状态')),'failed lock emits rollback notice');
  await sleep(240);
  ok(r.calls.fetch.length>=2,'failed lock schedules rollback persistence');
  const rollback=parseSave(r.calls.fetch.at(-1));
  ok(!rollback?.financeMonthLocks?.[r.month],'rollback persistence cannot resurrect failed lock');
  ok(!rollback?.auditLogs?.some(row=>row.action==='完成财务月结'),'rollback persistence cannot resurrect false lock audit');
  ok(rollback?.auditLogs?.some(row=>row.id==='audit-unrelated-lock'),'rollback persistence preserves unrelated audit');
}

// Failed unlock restores the exact previous accounting protection and its frozen
// snapshot, while removing only the failed unlock audit.
{
  const r=makeRuntime({locked:true,behavior:'fail-first'});
  r.subject.toggleFinanceMonthLock(r.month);
  const confirm=r.getConfirm();ok(typeof confirm==='function','failed-unlock confirmation missing');
  const pending=confirm();
  const unrelated={id:'audit-unrelated-unlock',action:'并发审计',target:'keep'};r.subject.auditLogs.push(unrelated);
  await pending;
  ok(Object.hasOwn(r.subject.financeMonthLocks,r.month),'failed unlock restores lock');
  ok(Object.hasOwn(r.subject.financeMonthSnapshots,r.month),'failed unlock restores frozen snapshot');
  eq(r.subject.financeMonthLocks[r.month].lockedAt,r.existingLock.lockedAt,'failed unlock restores original lock');
  eq(r.subject.financeMonthSnapshots[r.month].createdAt,r.existingSnapshot.createdAt,'failed unlock restores original snapshot');
  ok(!r.subject.auditLogs.some(row=>row.action==='解除财务月结'),'failed unlock removes attempt audit');
  ok(r.subject.auditLogs.includes(unrelated),'failed unlock preserves unrelated audit by identity');
  ok(!r.calls.notify.some(message=>message.includes('已解锁')),'failed unlock never emits success');
  ok(r.calls.notify.some(message=>message.includes('解锁未完成')&&message.includes('已恢复月结锁定')),'failed unlock emits rollback notice');
  await sleep(240);
  ok(r.calls.fetch.length>=2,'failed unlock schedules rollback persistence');
  const rollback=parseSave(r.calls.fetch.at(-1));
  ok(Boolean(rollback?.financeMonthLocks?.[r.month]),'rollback persistence restores lock in cloud payload');
  ok(Boolean(rollback?.financeMonthSnapshots?.[r.month]),'rollback persistence restores snapshot in cloud payload');
  ok(!rollback?.auditLogs?.some(row=>row.action==='解除财务月结'),'rollback persistence cannot resurrect false unlock audit');
  ok(rollback?.auditLogs?.some(row=>row.id==='audit-unrelated-unlock'),'rollback persistence preserves unrelated audit');
}

// Fail closed if the adapter barrier is absent rather than silently reverting to the
// historical debounced-success behavior.
{
  let confirm=null;const notifications=[];
  const s={
    toggleFinanceMonthLock:toggle,currentUser:{name:'Finance',role:'FINANCE'},financeMonthLocks:{},financeMonthSnapshots:{},auditLogs:[],
    canManageFinance:()=>true,isMonthLocked:()=>false,ensureAutomaticReceivables:()=>{},ensureAutomaticAssetCosts:()=>{},
    runFinanceMonthCheck:()=>({issues:[]}),getFinanceMonthCheck:()=>({issues:[]}),buildFinanceMonthSnapshot:()=>({createdAt:'x'}),
    askConfirm:(_config,action)=>{confirm=action;},logAudit:()=>fail('barrier-missing path must not audit'),persist:()=>fail('barrier-missing path must not persist'),notify:message=>notifications.push(String(message)),
  };
  s.toggleFinanceMonthLock('2026-09');ok(typeof confirm==='function','barrier-missing confirmation missing');await confirm();
  ok(!Object.hasOwn(s.financeMonthLocks,'2026-09'),'barrier-missing lock remains unchanged');
  ok(notifications.some(message=>message.includes('持久化服务不可用')),'barrier-missing path notifies fail-closed');
}

console.log('BUSINESS_FINANCE_MONTH_LOCK_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; lock+unlock=success-after-save-ack; failure=month-state+attempt-audit-rollback; concurrent-unrelated-audit=preserved; rollback-persist=failed-operation-not-resurrected; missing-barrier=fail-closed');
