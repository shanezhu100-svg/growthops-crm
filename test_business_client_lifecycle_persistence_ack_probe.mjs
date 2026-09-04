import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${['archiveClient','restoreClient','deleteLead'].map(extractMethod).join(',')}})`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: final methods not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LIFECYCLE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

function makeRuntime({kind,first}){
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const window={__growthOpsVm:subject,location:{hash:'#clients'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  const activeClient={id:'client-1',name:'Client One',archived:false,status:'ACTIVE',archivedAt:''};
  const archivedClient={id:'client-1',name:'Client One',archived:true,status:'PAUSED',archivedAt:'2026-08-01T00:00:00.000Z'};
  const lead={id:'lead-1',company:'Lead One',stage:'NEW'};
  Object.assign(subject,methods,{
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},
    clients:[clone(kind==='restore'?archivedClient:activeClient)],leads:[clone(lead)],openingProviders:[],openingDeals:[],financeCosts:[],auditLogs:[],backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    canArchiveClients:()=>true,
    askConfirm:(config,action)=>{subject.__confirm={config,action}},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    collectBackupPayload:()=>({clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeCosts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeReceivables:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  const target=kind==='lead'?subject.leads[0]:subject.clients[0];
  return {subject,target,calls,resolveFirst:status=>gate?.resolve(response(status))};
}

async function confirm(subject){if(typeof subject.__confirm?.action!=='function')throw new Error('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FAILED: confirmation callback missing');subject.__confirm.action();}
const findings=[];
const finding=label=>findings.push(label);
const successNotice=(kind,calls)=>calls.notify.some(m=>kind==='archive'?m.includes('已归档'):kind==='restore'?m.includes('已恢复'):m.includes('已删除'));
const invoke=(kind,subject,target)=>kind==='archive'?subject.archiveClient(target):kind==='restore'?subject.restoreClient(target):subject.deleteLead(target);
const attemptAction=kind=>kind==='archive'?'归档客户':kind==='restore'?'恢复归档客户':'删除潜在客户';

for(const kind of ['archive','restore','lead']){
  const {subject,target,calls,resolveFirst}=makeRuntime({kind,first:'deferred'});
  invoke(kind,subject,target);await confirm(subject);await sleep(210);
  if(calls.fetch.length===1&&successNotice(kind,calls))finding(`${kind}-success-before-ack`);
  resolveFirst(200);await sleep(20);
}

for(const kind of ['archive','restore','lead']){
  const {subject,target,calls}=makeRuntime({kind,first:'fail'});
  invoke(kind,subject,target);await confirm(subject);await sleep(240);
  const action=attemptAction(kind);
  const auditRemains=subject.auditLogs.some(a=>a.action===action);
  const localRemains=kind==='archive'?subject.clients[0]?.archived===true:kind==='restore'?subject.clients[0]?.archived===false:subject.leads.every(l=>String(l.id)!=='lead-1');
  if(localRemains&&auditRemains)finding(`${kind}-failed-save-local-state-remains`);
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const cloudRemains=kind==='archive'?later.clients?.[0]?.archived===true:kind==='restore'?later.clients?.[0]?.archived===false:(later.leads||[]).every(l=>String(l.id)!=='lead-1');
  if(cloudRemains&&(later.auditLogs||[]).some(a=>a.action===action))finding(`${kind}-later-persist-resurrects-failed-operation`);
}

if(findings.length){
  console.error(`BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(';')}`);
  process.exitCode=1;
}else console.log('BUSINESS_CLIENT_LIFECYCLE_PERSISTENCE_ACK_PROBE_SAFE: archive+restore+lead-delete success waits for ACK; failed saves rollback state+attempt-audit; later persist cannot resurrect');
