import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AD_PERSISTED_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_AD_PERSISTED_MUTATIONS_FAILED: ${name} not found`);
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
  throw new Error(`BUSINESS_AD_PERSISTED_MUTATIONS_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${['deleteAdDataRecord','saveAdSpend','saveAdsPlan'].map(extractMethod).join(',')}})`,{Number,String,Object,Array,Math,JSON,Date,Set},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_AD_PERSISTED_MUTATIONS_FAILED: compile: ${error.message}`)}
const fail=m=>{throw new Error('BUSINESS_AD_PERSISTED_MUTATIONS_FAILED: '+m)};
const eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${b}; actual=${a}`)};
const ok=(v,m)=>{if(!v)fail(m)};

function deletionSubject({records=null,lockSequence=[true,true]}={}){
  const record={id:'r1',date:'2026-08-31',spend:12,currency:'USD'};
  const account={accountName:'Account',adAccountId:'acct-1',adDataRecords:records??[{...record}]};
  const counters={persist:0,audit:0,accountSync:0,clientSync:0,notify:[],confirm:null,lockCalls:0};
  const s=Object.assign({},methods,{selectedAdsClient:{name:'Client'},selectedAdsAccount:account,selectedAdsPlatform:'FB',editingAdDataRecordId:null,
    assertMonthUnlocked(){const value=lockSequence[Math.min(counters.lockCalls,lockSequence.length-1)];counters.lockCalls+=1;return value;},
    askConfirm(_options,cb){counters.confirm=cb;},formatMoney(v,c){return `${c}:${v}`;},syncAccountAnalyticsFromRecords(){counters.accountSync+=1;},syncClientPlatformAnalytics(){counters.clientSync+=1;},persist(){counters.persist+=1;},logAudit(){counters.audit+=1;},notify(m){counters.notify.push(String(m));}});
  return {s,record,account,counters};
}

// Lock can change while the confirmation dialog is open. The callback must re-check.
{
  const {s,record,account,counters}=deletionSubject({lockSequence:[true,false]});
  s.deleteAdDataRecord(record);
  ok(typeof counters.confirm==='function','delete should request confirmation when initially unlocked');
  counters.confirm();
  eq(account.adDataRecords.length,1,'delete must not remove record after month becomes locked');
  eq(counters.persist,0,'locked-at-confirm delete must not persist');
  eq(counters.audit,0,'locked-at-confirm delete must not audit success');
}

// Stale records must not produce a false successful delete.
{
  const {s,record,account,counters}=deletionSubject({records:[],lockSequence:[true,true]});
  s.deleteAdDataRecord(record);
  if(counters.confirm)counters.confirm();
  eq(account.adDataRecords.length,0,'stale delete keeps record set unchanged');
  eq(counters.persist,0,'stale delete must not persist');
  eq(counters.audit,0,'stale delete must not audit success');
  ok(counters.notify.some(m=>m.includes('不存在')||m.includes('刷新')),'stale delete should explain stale target');
}

// Valid unlocked delete still performs one atomic durable write.
{
  const {s,record,account,counters}=deletionSubject({lockSequence:[true,true]});
  s.deleteAdDataRecord(record);counters.confirm();
  eq(account.adDataRecords.length,0,'valid delete removes exactly the target');
  eq(counters.persist,1,'valid delete persists once');
  eq(counters.audit,1,'valid delete audits once');
  eq(counters.accountSync,1,'valid delete syncs account analytics once');
  eq(counters.clientSync,1,'valid delete syncs client analytics once');
}

function spendSubject(value){
  const account={adSpend:value,adSpendCurrency:''};const counters={persist:0,notify:[]};
  const s=Object.assign({},methods,{persist(){counters.persist+=1;},notify(m){counters.notify.push(String(m));}});return {s,account,counters};
}
for(const bad of [-1,'not-a-number','Infinity',Number.POSITIVE_INFINITY]){
  const {s,account,counters}=spendSubject(bad);const before=account.adSpend;s.saveAdSpend(account);
  eq(account.adSpend,before,`invalid adSpend must remain unchanged: ${String(bad)}`);eq(counters.persist,0,`invalid adSpend must not persist: ${String(bad)}`);
}
{
  const {s,account,counters}=spendSubject('12.5');s.saveAdSpend(account);eq(account.adSpend,12.5,'valid adSpend normalized to number');eq(account.adSpendCurrency,'USD','valid adSpend defaults currency');eq(counters.persist,1,'valid adSpend persists once');
}

function planSubject(campaign){
  const counters={persist:0,audit:0,notify:[]};const s=Object.assign({},methods,{selectedAdsClient:{name:'Client'},localDateKey(){return '2026-09-03';},persist(){counters.persist+=1;},logAudit(){counters.audit+=1;},notify(m){counters.notify.push(String(m));}});return {s,counters};
}
const basePlan=()=>({planName:'Plan',name:'Campaign',adSets:[{ageMin:18,ageMax:65,budget:10}],isSaved:false,savedAt:'',updatedAt:''});
for(const mutate of [
  p=>p.adSets[0].budget='not-a-number',p=>p.adSets[0].budget=-1,p=>p.adSets[0].budget='Infinity',
  p=>p.adSets[0].ageMin='abc',p=>p.adSets[0].ageMin=17,p=>p.adSets[0].ageMax=66,p=>{p.adSets[0].ageMin=50;p.adSets[0].ageMax=30;}
]){
  const p=basePlan();mutate(p);const before=JSON.stringify(p);const {s,counters}=planSubject(p);s.saveAdsPlan(p);eq(JSON.stringify(p),before,'invalid ad plan must remain unchanged');eq(counters.persist,0,'invalid ad plan must not persist');eq(counters.audit,0,'invalid ad plan must not audit');
}
{
  const p=basePlan();p.adSets[0].budget='12.5';p.adSets[0].ageMin='20';p.adSets[0].ageMax='60';const {s,counters}=planSubject(p);s.saveAdsPlan(p);eq(p.adSets[0].budget,12.5,'valid plan budget normalized');eq(p.adSets[0].ageMin,20,'valid plan min age normalized');eq(p.adSets[0].ageMax,60,'valid plan max age normalized');eq(p.isSaved,true,'valid plan marked saved');eq(counters.persist,1,'valid plan persists once');eq(counters.audit,1,'valid plan audits once');
}

console.log('BUSINESS_AD_PERSISTED_MUTATIONS_OK: delete=stale-fail-closed+month-lock-rechecked-on-confirm+single-write; adSpend=finite-nonnegative; plan=budget-finite-nonnegative+age-18-65+ordered; valid-normalization+persist-audit=preserved; provenance=final-shipped-vm');
