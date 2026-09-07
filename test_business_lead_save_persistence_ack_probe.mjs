import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
const adapterPath=path.join(root,'dist','cloud-adapter.js');
if(!fs.existsSync(appDir)||!fs.existsSync(adapterPath))throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: final artifacts missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: ${name} missing`);
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
  throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: ${name} closing brace missing`);
}

let saveLead;
try{saveLead=vm.runInNewContext(`({${extractMethod('saveLead')}}).saveLead`,{Date,Math,Number,String,Object,Array,JSON,Set,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: final saveLead not executable: ${error.message}`)}

const adapter=fs.readFileSync(adapterPath,'utf8');
const bootAnchor='\n  boot();\n})();';
if(adapter.split(bootAnchor).length!==2)throw new Error('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: adapter boot anchor drifted');
const harnessAdapter=adapter.replace(bootAnchor,'\n})();');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clone=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function response(status){return {ok:status>=200&&status<300,status,json:async()=>status>=200&&status<300?({revision:status}):({message:'SYNTHETIC_LEAD_SAVE_FAILED'})}}
function parseState(call){const body=JSON.parse(call?.body||'{}');if(body.rpc!=='crm_save_state')throw new Error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FAILED: unexpected rpc=${body.rpc}`);return body.args?.p_state||{}}

function makeRuntime({kind='create',first='fail'}={}){
  const calls={fetch:[],notify:[]};const subject={};let saveAttempt=0,auditId=0;
  const gate=first==='deferred'?deferred():null;
  const window={__growthOpsVm:subject,location:{hash:'#leads'}};
  const document={documentElement:{classList:{remove:()=>{},add:()=>{}}},body:{appendChild:()=>{}},createElement:()=>({click(){},remove(){}})};
  const fetchMock=async(url,options={})=>{calls.fetch.push({url:String(url),body:String(options.body||'')});saveAttempt+=1;if(saveAttempt===1){if(first==='fail')return response(503);if(first==='deferred')return gate.promise;}return response(200)};
  vm.runInNewContext(harnessAdapter,{window,document,localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},FileReader:class{},Blob,TextEncoder,structuredClone:globalThis.structuredClone,crypto:globalThis.crypto,console,setTimeout,clearTimeout,Date,Math,JSON,String,Number,Object,Array,Promise,Error,fetch:fetchMock},{timeout:1000});
  const existing={id:'lead-save-1',company:'Before Lead',contact:'Old',stage:'QUALIFIED',source:'网站询盘',platformInterest:'FB+TK',budgetCurrency:'USD',expectedBudget:100,quoteCurrency:'USD',adQuote:50,nextFollowUp:'2026-09-10',convertedClientId:null,convertedAt:'',createdAt:'2026-09-01'};
  const survivor={id:'lead-survivor',company:'Survivor',stage:'NEW',createdAt:'2026-09-01'};
  const form=kind==='edit'?{...existing,company:'After Lead Edit',expectedBudget:'120'}:{id:null,company:'Created Lead',contact:'New',stage:'NEW',source:'网站询盘',platformInterest:'TK',budgetCurrency:'USD',expectedBudget:'500',quoteCurrency:'USD',adQuote:'0',nextFollowUp:'2026-09-12',convertedClientId:null,convertedAt:''};
  Object.assign(subject,{
    saveLead,leads:kind==='edit'?[existing,survivor]:[survivor],clients:[],financeReceivables:[],financeCosts:[],openingProviders:[],openingDeals:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:[],backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[],
    leadForm:clone(form),showLeadModal:true,leadPoolFilter:'ACTIVE',leadQuickFilter:'ALL',
    currentUser:{id:'admin',name:'Admin',role:'ADMIN',enabled:true},accountUid:()=> 'lead-created-1',localDateKey:()=> '2026-09-07',leadStageText:v=>String(v),ensureDailyBackup:()=>{},
    logAudit:(action,target)=>{const row={id:`audit-${++auditId}`,action:String(action),target:String(target)};subject.auditLogs.push(row);return row},notify:m=>calls.notify.push(String(m)),
    collectBackupPayload:()=>({clients:[],leads:clone(subject.leads),openingProviders:[],openingDeals:[],financeReceivables:[],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],auditLogs:clone(subject.auditLogs),backupSnapshots:[],financeMonthLocks:{},financeMonthSnapshots:{},financeReconciliations:[],financeActualRebates:[]}),
  });
  return {subject,calls,resolveFirst:status=>gate?.resolve(response(status))};
}

const findings=[];const finding=x=>findings.push(x);
const successUi=(subject,calls)=>subject.showLeadModal===false||calls.notify.some(m=>m.includes('已保存'));
for(const kind of ['create','edit']){
  const {subject,calls,resolveFirst}=makeRuntime({kind,first:'deferred'});
  subject.saveLead();await sleep(210);
  if(calls.fetch.length===1&&successUi(subject,calls))finding(`${kind}-success-before-ack`);
  resolveFirst(200);await sleep(20);
}
for(const kind of ['create','edit']){
  const {subject,calls}=makeRuntime({kind,first:'fail'});
  subject.saveLead();await sleep(240);
  const local=kind==='edit'?subject.leads.find(x=>x.id==='lead-save-1'):subject.leads.find(x=>x.company==='Created Lead');
  if(local&&subject.auditLogs.length>0)finding(`${kind}-failed-save-local-state-remains`);
  subject.persist();await sleep(240);
  const later=parseState(calls.fetch.at(-1));
  const persisted=kind==='edit'?(later.leads||[]).find(x=>x.id==='lead-save-1'&&x.company==='After Lead Edit'):(later.leads||[]).find(x=>x.company==='Created Lead');
  if(persisted&&(later.auditLogs||[]).length>0)finding(`${kind}-later-persist-resurrects-failed-save`);
}

if(findings.length){console.error(`BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_FINDINGS: count=${findings.length}; ${findings.join(';')}`);process.exitCode=1}
else console.log('BUSINESS_LEAD_SAVE_PERSISTENCE_ACK_PROBE_SAFE: create+edit success waits for ACK; failed save rolls back lead+attempt-audit; later persist cannot resurrect');
