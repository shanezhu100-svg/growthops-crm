import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: ${name} missing`);
  const start=match.index+match[0].indexOf(match[1]),open=bundle.indexOf('{',start);
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
  throw new Error(`BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: ${name} closing brace missing`);
}

let openConvertedLeadClient;
try{openConvertedLeadClient=vm.runInNewContext(`({${extractMethod('openConvertedLeadClient')}}).openConvertedLeadClient`,{Date,Math,Number,String,Object,Array,JSON,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: final method not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
const fail=message=>{throw new Error('BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_FAILED: '+message)};
const ok=(value,label)=>{if(!value)fail(label)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LINK_REPAIR_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')fail(`unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}
const byId=(rows,id)=>Array.isArray(rows)?rows.find(row=>String(row?.id??'')===String(id)):undefined;

function makeRuntime({first='fail',withBarrier=true,withClient=false}={}){
  const calls={fetch:[],notify:[],navigate:[]};const subject={};let attempt=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#leads'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});attempt+=1;if(attempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  if(!withBarrier)delete subject.persistLeadLinkRepairBarrier;
  const target={id:'lead-link-1',company:'Linked Lead',convertedClientId:'client-gone',convertedAt:'2026-09-01T00:00:00.000Z',stage:'WON'};
  const survivor={id:'lead-other',company:'Other Lead',convertedClientId:null,convertedAt:'',stage:'NEW'};
  Object.assign(subject,{
    openConvertedLeadClient,leads:[target,survivor],clients:withClient?[{id:'client-gone',name:'Existing Client'}]:[],
    openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    notify:m=>calls.notify.push(String(m)),navigateTo:p=>calls.navigate.push(String(p)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,target,survivor,resolveFirst:status=>gate?.resolve(response(status))};
}
async function waitFirstSave(calls){for(let i=0;i<40&&calls.fetch.length===0;i+=1)await sleep(10);eq(calls.fetch.length,1,'exactly one pending repair save before ACK')}
async function waitRollback(calls){for(let i=0;i<40&&calls.fetch.length<2;i+=1)await sleep(10);ok(calls.fetch.length>=2,'failed repair must persist rollback truth');return parseState(calls.fetch.at(-1))}

// A still-existing linked client remains a pure navigation path with no persistence.
{
  const {subject,calls,target}=makeRuntime({withClient:true,first:'fail'});
  subject.openConvertedLeadClient(target);
  eq(calls.fetch.length,0,'existing link performs no save');eq(subject.selectedClientId,'client-gone','existing link selects client');eq(calls.navigate[0],'client-detail','existing link navigates to client detail');
}

// Missing-link repair is tentative until the exact cleared-link state is ACKed.
{
  const {subject,calls,target,resolveFirst}=makeRuntime({first:'deferred'});
  const task=subject.openConvertedLeadClient(target);ok(task&&typeof task.then==='function','missing-link repair exposes ACK promise');await waitFirstSave(calls);
  eq(target.convertedClientId,null,'tentative repair clears converted id');eq(target.convertedAt,'','tentative repair clears converted timestamp');eq(calls.notify.length,0,'repair success message held before ACK');
  const pending=parseState(calls.fetch[0]);eq(byId(pending.leads,target.id)?.convertedClientId,null,'pending cloud state contains cleared link');
  resolveFirst(200);await task;eq(calls.fetch.length,1,'successful repair uses one durable save');ok(calls.notify.some(m=>m.includes('已不存在')), 'missing-client message emitted after ACK');
}

// Failed ACK restores the stale persisted link locally and in cloud rollback truth.
{
  const {subject,calls,target}=makeRuntime({first:'fail'});const beforeId=target.convertedClientId,beforeAt=target.convertedAt;
  await subject.openConvertedLeadClient(target);
  eq(target.convertedClientId,beforeId,'failed repair restores converted id');eq(target.convertedAt,beforeAt,'failed repair restores converted timestamp');ok(calls.notify.some(m=>m.includes('修复未保存')),'failed repair explains persistence failure');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,target.id)?.convertedClientId,beforeId,'rollback cloud restores converted id');eq(byId(rollback.leads,target.id)?.convertedAt,beforeAt,'rollback cloud restores converted timestamp');
}

// Newer same-ID replacement authority must survive a failed stale repair.
{
  const {subject,calls,target,resolveFirst}=makeRuntime({first:'deferred'});const task=subject.openConvertedLeadClient(target);await waitFirstSave(calls);
  const replacement={id:target.id,company:'Concurrent Lead',convertedClientId:'client-new',convertedAt:'2026-09-07T00:00:00.000Z',stage:'WON'};subject.leads.splice(0,1,replacement);
  resolveFirst(503);await task;eq(byId(subject.leads,target.id),replacement,'same-ID replacement remains authoritative locally');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,target.id)?.convertedClientId,'client-new','same-ID replacement reaches rollback cloud truth');
}

// A concurrent field-level relink on the same live object also wins over rollback.
{
  const {subject,calls,target,resolveFirst}=makeRuntime({first:'deferred'});const task=subject.openConvertedLeadClient(target);await waitFirstSave(calls);
  target.convertedClientId='client-concurrent';target.convertedAt='2026-09-07T01:00:00.000Z';resolveFirst(503);await task;
  eq(target.convertedClientId,'client-concurrent','concurrent relink id preserved');eq(target.convertedAt,'2026-09-07T01:00:00.000Z','concurrent relink timestamp preserved');
  const rollback=await waitRollback(calls);eq(byId(rollback.leads,target.id)?.convertedClientId,'client-concurrent','concurrent relink reaches rollback cloud truth');
}

// Missing durability service fails closed before mutating the persisted link.
{
  const {subject,calls,target}=makeRuntime({first:'fail',withBarrier:false});const before=clone(target);const result=subject.openConvertedLeadClient(target);
  eq(result,undefined,'missing barrier returns synchronously');eq(calls.fetch.length,0,'missing barrier performs zero network saves');eq(target.convertedClientId,before.convertedClientId,'missing barrier preserves converted id');eq(target.convertedAt,before.convertedAt,'missing barrier preserves converted timestamp');ok(calls.notify.some(m=>m.includes('持久化服务不可用')),'missing barrier explains fail-closed state');
}

// A stale lead object that is no longer in the live collection cannot be repaired.
{
  const {subject,calls,target}=makeRuntime({first:'fail'});subject.leads=subject.leads.filter(row=>row!==target);subject.openConvertedLeadClient(target);
  eq(calls.fetch.length,0,'stale lead repair performs zero saves');ok(calls.notify.some(m=>m.includes('状态已变化')),'stale lead repair reports live-state drift');
}

console.log('BUSINESS_LEAD_LINK_REPAIR_PERSISTENCE_ACK_OK: authority=final-app+final-cloud-adapter; existing-link=navigation-only; missing-link=success-after-single-save-ACK; failure=link-rollback+rollback-persisted; concurrency=same-id+field-relink-preserved; missing-barrier+stale-lead=fail-closed');
