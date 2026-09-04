import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: final runtime ${name} not found`);
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
  throw new Error(`BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: ${name} closing brace missing`);
}

let methods;
try{methods=vm.runInNewContext(`({${extractMethod('saveOpeningProvider')}})`,{Number,String,Object,Array,Math,Set,JSON,Date,Promise},{timeout:1000})}
catch(error){throw new Error(`BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: unable to execute final method: ${error.message}`)}
if(typeof methods.saveOpeningProvider!=='function')throw new Error('BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: saveOpeningProvider not executable');

const fail=message=>{throw new Error('BUSINESS_OPENING_PROVIDER_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const ok=(value,label)=>{if(!value)fail(label)};
const clone=value=>JSON.parse(JSON.stringify(value));

const policy=(overrides={})=>({id:'policy-1',effectiveDate:'2026-09-01',rebateRate:12.5,rebatePolicy:'standard',...overrides});
const contact=(overrides={})=>({id:'contact-1',name:'Alice',rebatePolicies:[policy()],...overrides});
const form=(overrides={})=>({id:null,name:'Provider A',contacts:[contact()],notes:'',...overrides});
const provider=(overrides={})=>({...form({id:'provider-1'}),...overrides});

function subject(overrides={}){
  return Object.assign({},methods,{
    providerForm:form(),openingProviders:[],openingDeals:[],showProviderModal:true,
    canManageProviders:()=>true,accountUid:prefix=>`${prefix}-new`,
    normalizeOpeningProvider:value=>clone(value),persist:()=>{},persistOpeningProviderBarrier:async function(){return this.persist()},logAudit:()=>{},notify:()=>{},
    ...overrides,
  });
}

// A stale edit must fail closed before it mutates linked opening deals or records a
// false successful edit. This mirrors the stale-source rule already enforced for
// opening deals and client/lead edits.
{
  let persisted=0,audited=0;const notices=[];
  const linked={id:'deal-1',providerId:'missing-provider',contactId:'contact-1',partnerName:'Old Provider',contactName:'Old Contact',contactInfo:'kept'};
  const s=subject({
    providerForm:form({id:'missing-provider',name:'Stale Provider',contacts:[contact({name:'New Contact'})]}),
    openingProviders:[],openingDeals:[clone(linked)],
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:m=>notices.push(String(m)),
  });
  s.saveOpeningProvider();
  eq(s.openingProviders.length,0,'stale provider edit must not recreate source');
  eq(s.openingDeals[0].partnerName,'Old Provider','stale provider edit must not rewrite linked deal provider name');
  eq(s.openingDeals[0].contactName,'Old Contact','stale provider edit must not rewrite linked deal contact name');
  eq(s.openingDeals[0].contactInfo,'kept','stale provider edit must not clear linked deal contact info');
  eq(persisted,0,'stale provider edit must not persist');
  eq(audited,0,'stale provider edit must not audit success');
  eq(s.showProviderModal,true,'stale provider edit keeps editor open');
  ok(notices.some(m=>m.includes('不存在')||m.includes('刷新')),'stale provider edit should explain stale source');
}

// Rebate policy dates are durable finance policy history. Non-empty but impossible
// calendar dates must not enter provider state.
for(const badDate of ['2026-02-30','2026/09/01']){
  let persisted=0,audited=0;const notices=[];
  const s=subject({
    providerForm:form({contacts:[contact({rebatePolicies:[policy({effectiveDate:badDate})]})]}),
    persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:m=>notices.push(String(m)),
  });
  s.saveOpeningProvider();
  eq(s.openingProviders.length,0,`invalid policy date must not create provider: ${badDate}`);
  eq(persisted,0,`invalid policy date must not persist: ${badDate}`);
  eq(audited,0,`invalid policy date must not audit: ${badDate}`);
  eq(s.showProviderModal,true,`invalid policy date keeps editor open: ${badDate}`);
  ok(notices.some(m=>m.includes('日期')||m.includes('生效')),'invalid policy date should be explained');
}

// Existing percentage and per-contact same-day uniqueness boundaries remain enforced.
// Blank values normalize to the allowed 0% policy; non-numeric form text and
// non-finite/range-invalid numeric values must not persist.
for(const invalidRate of [-1,101,'not-a-number',Number.POSITIVE_INFINITY]){
  const s=subject({providerForm:form({contacts:[contact({rebatePolicies:[policy({rebateRate:invalidRate})]})]})});
  s.saveOpeningProvider();
  eq(s.openingProviders.length,0,`invalid rebate rate blocked: ${String(invalidRate)}`);
}
{
  const s=subject({providerForm:form({contacts:[contact({rebatePolicies:[policy({id:'p1'}),policy({id:'p2',rebateRate:15})]})]})});
  s.saveOpeningProvider();
  eq(s.openingProviders.length,0,'duplicate effective date within one contact blocked');
}

// Valid create allocates one provider id and completes only after the durable barrier.
{
  let persisted=0;const audits=[];
  const s=subject({persist:()=>{persisted+=1},logAudit:(a,t)=>audits.push([a,t])});
  await s.saveOpeningProvider();
  eq(s.openingProviders.length,1,'valid provider create inserts once');
  eq(s.openingProviders[0].id,'provider-new','valid provider create allocates id');
  eq(persisted,1,'valid provider create crosses durable barrier once');
  eq(audits.length,1,'valid provider create audits once');
  eq(audits[0][0],'新增开户商','valid provider create audit action');
  eq(s.showProviderModal,false,'valid provider create closes editor after ACK');
}

// Valid edit updates exactly the existing provider and propagates current names to
// linked opening deals without duplicating provider state, then waits for ACK.
{
  let persisted=0;const audits=[];
  const existing=provider({name:'Old Provider'});
  const s=subject({
    providerForm:form({id:'provider-1',name:'Provider Updated',contacts:[contact({name:'Alice Updated'})]}),
    openingProviders:[clone(existing)],
    openingDeals:[{id:'deal-1',providerId:'provider-1',contactId:'contact-1',partnerName:'Old Provider',contactName:'Alice',contactInfo:'legacy'}],
    persist:()=>{persisted+=1},logAudit:(a,t)=>audits.push([a,t]),
  });
  await s.saveOpeningProvider();
  eq(s.openingProviders.length,1,'valid provider edit does not duplicate');
  eq(s.openingProviders[0].name,'Provider Updated','valid provider edit updates provider');
  eq(s.openingDeals[0].partnerName,'Provider Updated','valid provider edit propagates provider name');
  eq(s.openingDeals[0].contactName,'Alice Updated','valid provider edit propagates contact name');
  eq(s.openingDeals[0].contactInfo,'','valid provider edit clears legacy contact info when contact matches');
  eq(persisted,1,'valid provider edit crosses durable barrier once');
  eq(audits.length,1,'valid provider edit audits once');
  eq(audits[0][0],'修改开户商资料','valid provider edit audit action');
  eq(s.showProviderModal,false,'valid provider edit closes editor after ACK');
}

console.log('BUSINESS_OPENING_PROVIDER_MUTATIONS_OK: stale-edit=fail-closed; policy-date=yyyy-mm-dd+calendar-valid; rebate-rate=0-100+nonfinite-deny; duplicate-date=blocked; create+edit=single-write+durable-ACK; linked-deal-name-sync=preserved; provenance=final-shipped-vm');
