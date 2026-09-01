import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: no final app-inline JS artifacts found');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const store=new Map();
const localStorage={
  get length(){return store.size},
  key(index){return [...store.keys()][index]??null},
  getItem(key){return store.has(String(key))?store.get(String(key)):null},
  setItem(key,value){store.set(String(key),String(value))},
  removeItem(key){store.delete(String(key))},
  clear(){store.clear()},
};

let methods;
try{
  methods=vm.runInNewContext(`({${extractMethod('deleteClient')}})`,{localStorage},{timeout:1000});
}catch(error){
  throw new Error(`BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: unable to execute final deleteClient runtime: ${error.message}`);
}
if(typeof methods.deleteClient!=='function')throw new Error('BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: deleteClient is not executable');

const fail=message=>{throw new Error('BUSINESS_CLIENT_DELETE_INTEGRITY_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const hasId=(rows,id,key='clientId')=>rows.some(row=>String(row?.[key]??'')===String(id));

{
  store.clear();
  for(const [key,value] of [
    ['growthOpsSop-1-FB:acct-2026-09-01','{"task":true}'],
    ['growthOpsSop-12-FB:other-2026-09-01','{"other":true}'],
    ['growthOpsSop-2-TK:acct-2026-09-01','{"other":true}'],
    ['sop-1-2026-09-01','{"legacy":true}'],
    ['unrelated-key','keep'],
  ])localStorage.setItem(key,value);

  const client={id:1,name:'Deleted Client',archived:true,fbAccounts:[{adDataRecords:[{}]}],tkAccounts:[],adCampaigns:[{}]};
  const survivor={id:2,name:'Survivor',archived:false};
  const linkedLead={id:'lead-1',stage:'WON',convertedClientId:1,convertedAt:'2026-08-01T00:00:00.000Z'};
  const unrelatedLead={id:'lead-2',stage:'WON',convertedClientId:2,convertedAt:'2026-08-02T00:00:00.000Z'};
  let persisted=0,audited=0,confirmed=0,syncs=0,notice='';
  const subject={
    deleteClient:methods.deleteClient,
    currentUser:{role:'ADMIN'},clients:[client,survivor],leads:[linkedLead,unrelatedLead],
    openingDeals:[{id:'o1',clientId:1},{id:'o2',clientId:2}],
    financeReceivables:[{id:'r1',clientId:1,payments:[]},{id:'r2',clientId:2,payments:[]}],
    financeCosts:[{id:'c1',clientId:1},{id:'c2',clientId:2}],
    standaloneAlerts:[{id:'a1',clientId:1},{id:'a2',clientId:2}],
    dismissedAlerts:[{id:'d1',clientId:1},{id:'d2',clientId:2}],
    mediaTools:[{id:'t1',bindings:[{clientId:1,accountKey:'ALL'},{clientId:2,accountKey:'ALL'}]}],
    financeMonthSnapshots:{},
    selectedClientId:1,selectedAssetsClientId:1,selectedSopClientId:1,selectedAnalyticsClientId:1,selectedAdsClientId:1,
    clientRelationSummary:()=>({adRecords:1,campaigns:1,openings:1,receivables:1,costs:1,tools:1,total:6}),
    askConfirm:(opts,callback)=>{confirmed+=1;callback()},
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:msg=>{notice=msg},
    syncAnalyticsAccountSelection:()=>{syncs+=1},syncAdsAccountSelection:()=>{syncs+=1},syncSopAccountSelection:()=>{syncs+=1},
  };

  subject.deleteClient(client);
  eq(confirmed,1,'allowed permanent delete confirms exactly once');
  eq(persisted,1,'allowed permanent delete persists exactly once');
  eq(audited,1,'allowed permanent delete audits exactly once');
  eq(syncs,3,'allowed permanent delete repairs all module selections');
  eq(subject.clients.length,1,'deleted client removed from client collection');
  eq(String(subject.clients[0].id),'2','unrelated client preserved');
  for(const [label,rows] of [
    ['opening deals',subject.openingDeals],['receivables',subject.financeReceivables],['costs',subject.financeCosts],
    ['standalone alerts',subject.standaloneAlerts],['dismissed alerts',subject.dismissedAlerts],
  ]){
    if(hasId(rows,1))fail(`${label} retained deleted-client reference`);
    if(!hasId(rows,2))fail(`${label} removed unrelated client data`);
  }
  eq(subject.mediaTools[0].bindings.length,1,'tool bindings remove only deleted client');
  eq(String(subject.mediaTools[0].bindings[0].clientId),'2','unrelated tool binding preserved');
  eq(linkedLead.convertedClientId,null,'converted lead pointer cleared immediately');
  eq(linkedLead.convertedAt,'','converted lead timestamp cleared immediately');
  eq(linkedLead.stage,'WON','historical WON lead stage remains unchanged');
  eq(String(unrelatedLead.convertedClientId),'2','unrelated converted lead pointer preserved');
  for(const key of ['growthOpsSop-1-FB:acct-2026-09-01','sop-1-2026-09-01']){
    eq(localStorage.getItem(key),null,`deleted client SOP key removed: ${key}`);
  }
  for(const key of ['growthOpsSop-12-FB:other-2026-09-01','growthOpsSop-2-TK:acct-2026-09-01','unrelated-key']){
    if(localStorage.getItem(key)===null)fail(`unrelated localStorage key removed: ${key}`);
  }
  for(const key of ['selectedClientId','selectedAssetsClientId','selectedSopClientId','selectedAnalyticsClientId','selectedAdsClientId']){
    eq(String(subject[key]),'2',`${key} falls back to surviving client`);
  }
  if(!notice.includes('已删除'))fail('success notification missing after permanent delete');
}

{
  store.clear();
  localStorage.setItem('growthOpsSop-1-FB:acct-2026-09-01','keep');
  const client={id:1,name:'Locked Client',archived:true};
  let confirmed=0,persisted=0,notified='';
  const linkedLead={id:'lead-lock',stage:'WON',convertedClientId:1,convertedAt:'2026-08-01T00:00:00.000Z'};
  const subject={
    deleteClient:methods.deleteClient,currentUser:{role:'ADMIN'},clients:[client],leads:[linkedLead],
    openingDeals:[],financeReceivables:[{id:'r1',clientId:1,payments:[{amount:1}]}],financeCosts:[],standaloneAlerts:[],dismissedAlerts:[],mediaTools:[],financeMonthSnapshots:{},
    askConfirm:()=>{confirmed+=1},persist:()=>{persisted+=1},notify:msg=>{notified=msg},
  };
  subject.deleteClient(client);
  eq(confirmed,0,'payment-history blocker prevents confirmation');
  eq(persisted,0,'payment-history blocker prevents persistence');
  eq(subject.clients.length,1,'payment-history blocker preserves client');
  eq(String(linkedLead.convertedClientId),'1','payment-history blocker preserves lead link');
  if(localStorage.getItem('growthOpsSop-1-FB:acct-2026-09-01')===null)fail('payment-history blocker removed SOP progress');
  if(!/不能永久删除/.test(notified))fail('payment-history blocker notification missing');
}

console.log('BUSINESS_CLIENT_DELETE_INTEGRITY_OK: permanent-delete=cascade+lead-pointer+SOP-cleanup; unrelated-data=preserved; won-history=preserved; payment-history=blocks-without-side-effects');
