import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: ${name} closing brace missing`);
}

const storage=new Map();
const localStorage={
  get length(){return storage.size},
  key(index){return [...storage.keys()][index]??null},
  getItem(key){return storage.has(String(key))?storage.get(String(key)):null},
  setItem(key,value){storage.set(String(key),String(value))},
  removeItem(key){storage.delete(String(key))},
  clear(){storage.clear()},
};

let deleteClient;
try{deleteClient=vm.runInNewContext(`({${extractMethod('deleteClient')}}).deleteClient`,{localStorage,Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: final deleteClient not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_CLIENT_DELETE_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

function makeRuntime(first){
  storage.clear();
  localStorage.setItem('growthOpsSop-1-FB:acct-2026-09-01','attempt-sop');
  localStorage.setItem('growthOpsSop-2-FB:other-2026-09-01','survivor-sop');
  const calls={fetch:[],notify:[]};
  const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#clients'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{
    calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;
    if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}
    return response(200);
  };
  vm.runInNewContext(harnessAdapter,{window,document,localStorage,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone,crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  const client={id:1,name:'Deleted Client',archived:true,fbAccounts:[{adDataRecords:[{}]}],tkAccounts:[],adCampaigns:[{}]};
  const survivor={id:2,name:'Survivor',archived:false};
  const linkedLead={id:'lead-1',stage:'WON',convertedClientId:1,convertedAt:'2026-08-01T00:00:00.000Z'};
  const unrelatedLead={id:'lead-2',stage:'WON',convertedClientId:2,convertedAt:'2026-08-02T00:00:00.000Z'};
  Object.assign(subject,{
    deleteClient,
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},
    clients:[client,survivor],leads:[linkedLead,unrelatedLead],
    openingProviders:[],openingDeals:[{id:'o1',clientId:1},{id:'o2',clientId:2}],
    financeReceivables:[{id:'r1',clientId:1,payments:[]},{id:'r2',clientId:2,payments:[]}],
    financeCosts:[{id:'c1',clientId:1},{id:'c2',clientId:2}],
    standaloneAlerts:[{id:'a1',clientId:1},{id:'a2',clientId:2}],dismissedAlerts:[{id:'d1',clientId:1},{id:'d2',clientId:2}],
    mediaTools:[{id:'t1',bindings:[{clientId:1,accountKey:'ALL'},{clientId:2,accountKey:'ALL'}]}],
    auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    selectedClientId:1,selectedAssetsClientId:1,selectedSopClientId:1,selectedAnalyticsClientId:1,selectedAdsClientId:1,
    clientRelationSummary:()=>({adRecords:1,campaigns:1,openings:1,receivables:1,costs:1,tools:1,total:6}),
    askConfirm:(config,action)=>{subject.__confirm={config,action}},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},
    notify:m=>calls.notify.push(String(m)),ensureDailyBackup:()=>{},
    syncAnalyticsAccountSelection:()=>{},syncAdsAccountSelection:()=>{},syncSopAccountSelection:()=>{},
    collectBackupPayload:()=>({
      clients:clone(subject.clients),leads:clone(subject.leads),openingProviders:clone(subject.openingProviders),openingDeals:clone(subject.openingDeals),
      financeCosts:clone(subject.financeCosts),financeReceivables:clone(subject.financeReceivables),standaloneAlerts:clone(subject.standaloneAlerts),dismissedAlerts:clone(subject.dismissedAlerts),mediaTools:clone(subject.mediaTools),
      auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    }),
  });
  return {subject,client,calls,resolveFirst:status=>gate?.resolve(response(status))};
}

function confirm(subject){if(typeof subject.__confirm?.action!=='function')throw new Error('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FAILED: confirmation callback missing');return subject.__confirm.action()}
const findings=[];
const finding=label=>findings.push(label);
const successNotice=calls=>calls.notify.some(m=>m.includes('已删除'));
const hasClient=(rows,id)=>Array.isArray(rows)&&rows.some(row=>String(row?.id)===String(id));
const hasClientRef=(rows,id)=>Array.isArray(rows)&&rows.some(row=>String(row?.clientId??'')===String(id));

{
  const {subject,client,calls,resolveFirst}=makeRuntime('deferred');
  subject.deleteClient(client);const pending=confirm(subject);await sleep(210);
  if(calls.fetch.length===1&&successNotice(calls))finding('delete-success-before-ack');
  resolveFirst(200);await Promise.resolve(pending);await sleep(20);
}

{
  const {subject,client,calls}=makeRuntime('fail');
  subject.deleteClient(client);await Promise.resolve(confirm(subject));await sleep(240);
  if(!hasClient(subject.clients,1))finding('failed-save-client-remains-deleted');
  const linkedLead=subject.leads.find(row=>String(row?.id)==='lead-1');
  const cascadeStillApplied=!hasClientRef(subject.openingDeals,1)&&!hasClientRef(subject.financeReceivables,1)&&!hasClientRef(subject.financeCosts,1)&&!hasClientRef(subject.standaloneAlerts,1)&&!hasClientRef(subject.dismissedAlerts,1)&&linkedLead?.convertedClientId==null&&subject.mediaTools[0]?.bindings?.every(row=>String(row?.clientId)!=='1');
  if(cascadeStillApplied)finding('failed-save-related-cascade-remains');
  if(localStorage.getItem('growthOpsSop-1-FB:acct-2026-09-01')===null)finding('failed-save-sop-cleanup-remains');
  if(subject.auditLogs.some(row=>String(row?.action).includes('删除')))finding('failed-save-attempt-audit-remains');
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const laterLead=(later.leads||[]).find(row=>String(row?.id)==='lead-1');
  const laterResurrected=!hasClient(later.clients,1)&&!hasClientRef(later.openingDeals,1)&&laterLead?.convertedClientId==null&&(later.auditLogs||[]).some(row=>String(row?.action).includes('删除'));
  if(laterResurrected)finding('later-persist-resurrects-failed-delete');
}

if(findings.length){
  console.error(`BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(';')}`);
  process.exitCode=1;
}else console.log('BUSINESS_CLIENT_DELETE_PERSISTENCE_ACK_PROBE_SAFE: permanent delete success waits for ACK; failed save restores complete cascade+SOP+attempt-audit; later persist cannot resurrect');
