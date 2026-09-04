import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
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
    if(ch==='{')depth+=1;
    else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('saveOpeningProvider')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: final method not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_OPENING_PROVIDER_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

const policy=(overrides={})=>({id:'policy-1',effectiveDate:'2026-09-01',rebateRate:12.5,rebatePolicy:'standard',...overrides});
const contact=(overrides={})=>({id:'contact-1',name:'Alice',rebatePolicies:[policy()],...overrides});
const form=(overrides={})=>({id:null,name:'Provider A',contacts:[contact()],notes:'',...overrides});
const provider=(overrides={})=>({...form({id:'provider-1'}),...overrides});
const linkedDeal=(overrides={})=>({id:'deal-1',providerId:'provider-1',contactId:'contact-1',partnerName:'Provider Old',contactName:'Alice Old',contactInfo:'legacy',...overrides});

function makeRuntime({kind,first}){
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0,uid=0;
  const gate=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#account-opening'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  const existing=kind==='edit'?provider({name:'Provider Old'}):null;
  Object.assign(subject,methods,{
    currentUser:{id:'finance',name:'Finance User',role:'FINANCE',enabled:true},clients:[],openingProviders:existing?[clone(existing)]:[],openingDeals:existing?[linkedDeal()]:[],financeCosts:[],auditLogs:[],backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    providerForm:kind==='edit'?form({id:'provider-1',name:'Provider Updated',contacts:[contact({name:'Alice Updated'})]}):form(),showProviderModal:true,
    canManageProviders:()=>true,accountUid:prefix=>`${prefix}-${++uid}`,normalizeOpeningProvider:value=>clone(value),
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:[],openingProviders:clone(subject.openingProviders),openingDeals:clone(subject.openingDeals),financeCosts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,resolveFirst:status=>gate?.resolve(response(status))};
}

const findings=[];
const finding=label=>findings.push(label);

// Existing shipped behavior closes the provider editor immediately even though the
// real adapter save is still pending. That is the user-visible success boundary.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'create',first:'deferred'});
  subject.saveOpeningProvider();
  await sleep(210);
  if(calls.fetch.length===1&&subject.showProviderModal===false)finding('create-success-before-ack');
  resolveFirst(200);await sleep(20);
}

// A rejected first save currently leaves the created provider and its success audit
// live locally; a later ordinary persist can therefore commit that failed operation.
{
  const {subject,calls}=makeRuntime({kind:'create',first:'fail'});
  subject.saveOpeningProvider();await sleep(240);
  if(subject.openingProviders.length===1&&subject.auditLogs.some(a=>a.action==='新增开户商'))finding('create-failed-save-local-state-remains');
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  if((later.openingProviders||[]).length===1&&(later.auditLogs||[]).some(a=>a.action==='新增开户商'))finding('create-later-persist-resurrects-failed-operation');
}

// EDIT has the same premature UI completion while its provider and linked-deal name
// rewrite are only tentatively queued for persistence.
{
  const {subject,calls,resolveFirst}=makeRuntime({kind:'edit',first:'deferred'});
  subject.saveOpeningProvider();
  await sleep(210);
  if(calls.fetch.length===1&&subject.showProviderModal===false)finding('edit-success-before-ack');
  resolveFirst(200);await sleep(20);
}

// Failed EDIT currently leaves both the provider mutation and denormalized linked-deal
// rewrite plus the attempt audit live, so the next save can commit all three.
{
  const {subject,calls}=makeRuntime({kind:'edit',first:'fail'});
  subject.saveOpeningProvider();await sleep(240);
  const localProvider=subject.openingProviders.find(p=>p.id==='provider-1');
  const localDeal=subject.openingDeals.find(d=>d.id==='deal-1');
  if(localProvider?.name==='Provider Updated'&&localDeal?.partnerName==='Provider Updated'&&localDeal?.contactName==='Alice Updated'&&subject.auditLogs.some(a=>a.action==='修改开户商资料'))finding('edit-failed-save-local-state-remains');
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const persistedProvider=(later.openingProviders||[]).find(p=>p.id==='provider-1');
  const persistedDeal=(later.openingDeals||[]).find(d=>d.id==='deal-1');
  if(persistedProvider?.name==='Provider Updated'&&persistedDeal?.partnerName==='Provider Updated'&&(later.auditLogs||[]).some(a=>a.action==='修改开户商资料'))finding('edit-later-persist-resurrects-failed-operation');
}

if(findings.length){
  console.error(`BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(';')}`);
  process.exitCode=1;
}else{
  console.log('BUSINESS_OPENING_PROVIDER_PERSISTENCE_ACK_PROBE_SAFE: create+edit success waits for ACK; failed saves rollback source+linked-deal+attempt-audit; later persist cannot resurrect');
}
