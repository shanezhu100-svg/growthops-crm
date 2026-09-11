import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd(),appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_FAILED: final app missing');
const bundle=fs.readdirSync(appDir).filter(n=>/^app-inline-\d+\.js$/.test(n)).sort().map(n=>fs.readFileSync(path.join(appDir,n),'utf8')).join('\n');
function extractMethod(name){
  const match=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m').exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),open=bundle.indexOf('{',start);let depth=0,quote='',escaped=false,line=false,block=false;
  for(let i=open;i<bundle.length;i+=1){const ch=bundle[i],next=bundle[i+1]||'';if(line){if(ch==='\n')line=false;continue}if(block){if(ch==='*'&&next==='/'){block=false;i+=1}continue}if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}if(ch==='/'&&next==='/'){line=true;i+=1;continue}if(ch==='/'&&next==='*'){block=true;i+=1;continue}if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim()}
  throw new Error(`BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}
const external=new Set(['persist','persistClientSaveBarrier','logAudit','notify','navigateTo','ensureAutomaticAssetCosts','ensureAutomaticReceivables','ensureClientFirstReceivable']),pure=new Set(['localDateKey']),sources=new Map();
function collect(name){if(sources.has(name)||external.has(name)||pure.has(name))return;const source=extractMethod(name);sources.set(name,source);for(const m of source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)){const child=m[1];if(child!==name&&!external.has(child)&&!pure.has(child))collect(child)}}
collect('saveClient');
const context={Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,setTimeout,clearTimeout},methods={};
for(const [name,source] of sources){try{methods[name]=vm.runInNewContext(`({${source}})`,context,{timeout:1000})[name]}catch(e){throw new Error(`BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_FAILED: shipped ${name} not executable: ${e.message}`)}}
const clone=v=>JSON.parse(JSON.stringify(v)),fail=m=>{throw new Error('BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_FAILED: '+m)},ok=(v,l)=>{if(!v)fail(l)},eq=(a,e,l)=>{if(a!==e)fail(`${l}; expected=${e}; actual=${a}`)},same=(a,e,l)=>{if(JSON.stringify(a)!==JSON.stringify(e))fail(`${l}; expected=${JSON.stringify(e)}; actual=${JSON.stringify(a)}`)};
function deferred(){let resolve,reject;const promise=new Promise((res,rej)=>{resolve=res;reject=rej});return {promise,resolve,reject}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(r=>String(r?.id??'')===String(id)):undefined;
function makeRuntime(){
  const gate=deferred(),calls={notify:[],navigate:[],rollbackPersist:0,audit:0};
  const existing={id:'collection-client-1',name:'Before Save',archived:false,status:'ACTIVE',platform:['TK'],billingMode:'FULL_MONTH',monthlyFee:100,currency:'USD',startDate:'2026-09-01',renewalAlertDay:25,collectionPlan:{mode:'MONTHLY',firstDay:15,firstRatio:0.5},notes:'before',networkEnvironments:[],fbAccounts:[],tkAccounts:[{id:'tk-old'}],googleAccounts:[],instagramAccounts:[]};
  const survivor={id:'collection-survivor',name:'Survivor',archived:false,status:'ACTIVE',billingMode:'MANUAL',monthlyFee:0,currency:'USD',collectionPlan:{mode:'MONTHLY',firstDay:15,firstRatio:0.5}};
  const form={...clone(existing),name:'After Edit',monthlyFee:120,collectionPlan:{mode:'SEMI_MONTHLY',firstDay:12,firstRatio:0.4}};
  const s={};
  Object.assign(s,methods,{clients:[existing,survivor],leads:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[],openingProviders:[],openingDeals:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],form,formDirty:true,currentPage:'client-form',currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},selectedClientId:existing.id,selectedAssetsClientId:existing.id,selectedSopClientId:existing.id,selectedAnalyticsClientId:existing.id,selectedAdsClientId:existing.id,localDateKey:()=> '2026-09-01',$nextTick:fn=>fn?.(),ensureDailyBackup(){},persist(){calls.rollbackPersist+=1;return true},persistClientSaveBarrier:()=>gate.promise,logAudit:(action,target)=>{const row={id:`audit-${++calls.audit}`,action:String(action),target:String(target)};s.auditLogs.push(row);return row},notify:m=>calls.notify.push(String(m)),navigateTo:(...args)=>calls.navigate.push(args),ensureClientFirstReceivable:()=>0,ensureAutomaticReceivables:()=>0,ensureAutomaticAssetCosts:()=>0});
  return {s,gate,calls,existing};
}
async function start(runtime){const task=runtime.s.saveClient();ok(task?.then,'saveClient exposes ACK promise');const attempted=byId(runtime.s.clients,'collection-client-1');ok(attempted,'attempted client remains addressable');same(attempted.collectionPlan,{mode:'SEMI_MONTHLY',firstDay:12,firstRatio:0.4},'attempt applies normalized nested collection plan before ACK');return {task,attempted}}

{
  const r=makeRuntime(),before=clone(r.existing.collectionPlan),{task}=await start(r);r.gate.reject(new Error('synthetic collection plan save failure'));await task;same(byId(r.s.clients,'collection-client-1')?.collectionPlan,before,'failed ACK deep-restores persisted collection plan');same(r.s.form.collectionPlan,{mode:'SEMI_MONTHLY',firstDay:12,firstRatio:0.4},'failed ACK preserves retryable form collection plan');eq(r.calls.rollbackPersist,1,'failed ACK persists rollback truth exactly once');ok(r.calls.notify.some(m=>/未保存|失败/.test(m)),'failed ACK surfaces failure notice');
}
{
  const r=makeRuntime(),{task,attempted}=await start(r);attempted.collectionPlan={mode:'SEMI_MONTHLY',firstDay:21,firstRatio:0.3};r.gate.reject(new Error('synthetic concurrent collection edit'));await task;same(byId(r.s.clients,'collection-client-1')?.collectionPlan,{mode:'SEMI_MONTHLY',firstDay:21,firstRatio:0.3},'failed older ACK preserves newer nested client collection plan authority');eq(byId(r.s.clients,'collection-client-1')?.name,'Before Save','attempt-owned scalar field still rolls back independently');
}
{
  const r=makeRuntime(),{task}=await start(r);const attempt=byId(r.s.clients,'collection-client-1'),replacement={...clone(attempt),name:'Concurrent Replacement',collectionPlan:{mode:'SEMI_MONTHLY',firstDay:24,firstRatio:0.25}};r.s.clients.splice(r.s.clients.indexOf(attempt),1,replacement);r.gate.reject(new Error('synthetic replacement'));await task;eq(byId(r.s.clients,'collection-client-1'),replacement,'same-id client replacement remains authoritative on failed older ACK');same(replacement.collectionPlan,{mode:'SEMI_MONTHLY',firstDay:24,firstRatio:0.25},'replacement nested collection plan remains untouched');
}
{
  const r=makeRuntime(),{task}=await start(r);r.s.form.collectionPlan={mode:'SEMI_MONTHLY',firstDay:25,firstRatio:0.6};r.s.formDirty=true;r.gate.resolve(true);await task;same(r.s.form.collectionPlan,{mode:'SEMI_MONTHLY',firstDay:25,firstRatio:0.6},'successful older ACK preserves newer nested form collection plan edit');eq(r.s.formDirty,true,'newer form edit remains dirty after older ACK');eq(r.calls.rollbackPersist,0,'successful ACK has no rollback persist');
}

console.log('BUSINESS_CLIENT_COLLECTION_PLAN_PERSISTENCE_ACK_OK: nested-plan=deep-rollback; concurrency=field-CAS+same-id-replacement+new-form-edit-preserved; failed-ACK=rollback-persisted; success=ACK-gated');
