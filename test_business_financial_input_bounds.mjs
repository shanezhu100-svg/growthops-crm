import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_FINANCIAL_INPUT_BOUNDS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_FINANCIAL_INPUT_BOUNDS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_FINANCIAL_INPUT_BOUNDS_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_FINANCIAL_INPUT_BOUNDS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['defaultLeadForm','saveLead','saveClient'];
const methods=vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`,{Number,String,Object,Array,Math,Date},{timeout:1000});
const fail=message=>{throw new Error('BUSINESS_FINANCIAL_INPUT_BOUNDS_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};

function runLead(field,value){
  let persisted=0,audited=0,notified='';
  const leadForm={...methods.defaultLeadForm(),company:'Bounds Lead',expectedBudget:100,adQuote:20,[field]:value};
  const s=Object.assign({},methods,{
    leadForm,leads:[],showLeadModal:true,leadPoolFilter:'',leadQuickFilter:'',
    accountUid:()=> 'lead-bounds',localDateKey:()=> '2026-08-31',
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:msg=>{notified=String(msg??'')},leadStageText:v=>v,
  });
  s.saveLead();
  return {persisted,audited,notified,count:s.leads.length,modal:s.showLeadModal};
}

for(const [field,value,label] of [
  ['expectedBudget','-1','negative expected budget'],
  ['expectedBudget','abc','NaN expected budget'],
  ['expectedBudget','Infinity','infinite expected budget'],
  ['adQuote','-1','negative ad quote'],
  ['adQuote','abc','NaN ad quote'],
  ['adQuote','Infinity','infinite ad quote'],
]){
  const r=runLead(field,value);
  eq(r.persisted,0,`${label} must not persist`);
  eq(r.audited,0,`${label} must not audit success`);
  eq(r.count,0,`${label} must not insert lead`);
  eq(r.modal,true,`${label} keeps edits open`);
  if(!/有效|金额|预算|报价/.test(r.notified))fail(`${label} must show financial validation message; actual=${r.notified}`);
}

function runClient(monthlyFee){
  let persisted=0,audited=0,billing=0,navigated='',notified='';
  const s=Object.assign({},methods,{
    form:{id:null,sourceLeadId:null,name:'Bounds Client',billingMode:'FULL_MONTH',monthlyFee,currency:'USD'},
    clients:[],leads:[],formDirty:true,
    defaultForm:()=>({billingMode:'FULL_MONTH',monthlyFee:0,currency:'USD'}),
    cleanPlatformAccounts:()=>{},cleanNetworkEnvironments:()=>{},normalizeClient:value=>({...value}),
    ensureClientFirstReceivable:()=>{billing+=1;return 1},
    ensureAutomaticReceivables:()=>{billing+=1;return 1},
    ensureAutomaticAssetCosts:()=>{billing+=1;return 1},
    localDateKey:()=> '2026-08-31',persist:()=>{persisted+=1},persistClientSaveBarrier:()=>{persisted+=1;return Promise.resolve(true)},logAudit:()=>{audited+=1},
    formatMoney:(value,currency)=>`${currency}:${value}`,notify:msg=>{notified=String(msg??'')},navigateTo:page=>{navigated=page},
  });
  s.saveClient();
  return {persisted,audited,billing,navigated,notified,count:s.clients.length,dirty:s.formDirty};
}

for(const [value,label] of [['-1','negative monthly fee'],['abc','NaN monthly fee'],['Infinity','infinite monthly fee']]){
  const r=runClient(value);
  eq(r.persisted,0,`${label} must not persist`);
  eq(r.audited,0,`${label} must not audit success`);
  eq(r.billing,0,`${label} must not create billing/cost side effects`);
  eq(r.navigated,'',`${label} must not navigate away`);
  eq(r.count,0,`${label} must not insert client`);
  eq(r.dirty,true,`${label} keeps unsaved form state`);
  if(!/有效|金额|服务费/.test(r.notified))fail(`${label} must show financial validation message; actual=${r.notified}`);
}

// Zero remains valid for unquoted/free arrangements; existing positive paths are
// covered by the lead/client lifecycle gate.
let zero=runLead('expectedBudget','0');
eq(zero.persisted,1,'zero expected budget remains valid');
zero=runLead('adQuote','0');
eq(zero.persisted,1,'zero ad quote remains valid');
let zeroClient=runClient('0');
eq(zeroClient.persisted,1,'zero monthly fee remains valid through durable client-save barrier');

console.log('BUSINESS_FINANCIAL_INPUT_BOUNDS_OK: lead-budget+quote+client-fee=finite-nonnegative; negative+nan+infinity=denied-before-persist/audit/billing; zero=preserved+client-durable-ACK');