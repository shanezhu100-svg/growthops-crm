import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const securityPath=path.join(process.cwd(),'dist','cloud-security-hotfix.js');
if(!fs.existsSync(securityPath))throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: dist/cloud-security-hotfix.js missing; run canonical build first');
const source=fs.readFileSync(securityPath,'utf8');
const startMarker='  const resolveVisibleClientId=()=>{';
const endMarker='  function setRevealButtonState';
const start=source.indexOf(startMarker);
const end=source.indexOf(endMarker,start);
if(start<0||end<0)throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: final credential resolver boundaries not found');
const resolverBlock=source.slice(start,end).trim();
if(!resolverBlock.includes('const explicitAssetsClientId=vm.selectedAssetsClientId;'))throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: aggregate asset sentinel hardening missing from final resolver');

const factorySource=`(function(vm,document,window,cleanText,isAccountAssetPage){\n${resolverBlock}\nreturn {resolveVisibleClientId,resolveCredentialClientId};\n})`;
let factory;
try{
  factory=vm.runInNewContext(factorySource,Object.create(null),{timeout:1000});
}catch(error){
  throw new Error(`BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: unable to compile final resolver: ${error.message}`);
}

const makeElement=(text,visible=true)=>({
  textContent:text,
  getBoundingClientRect(){return visible?{width:120,height:24}:{width:0,height:0};},
});
function makeSubject(state,{visibleNames=[],bodyNames=visibleNames,assetPage=true}={}){
  const document={
    querySelectorAll(){return visibleNames.map(name=>makeElement(name));},
    body:{textContent:bodyNames.join(' ')},
  };
  const window={getComputedStyle(el){const rect=el.getBoundingClientRect();return {display:rect.width?'block':'none',visibility:rect.height?'visible':'hidden'};}};
  const cleanText=node=>String(node?.textContent??'').replace(/\s+/g,' ').trim();
  return factory(state,document,window,cleanText,()=>assetPage);
}
const eq=(actual,expected,label)=>{if(actual!==expected)throw new Error(`BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: ${label}; expected=${expected}; actual=${actual}`);};

const clients=[{id:'c1',name:'Alpha'},{id:'c2',name:'Beta'}];

// Aggregate mode is the highest-priority security/business boundary. The page may
// visibly contain every client name, but credential resolution must still return no
// concrete client and therefore must not target any client-scoped credential RPC.
{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:0,selectedClientId:'c1'},{visibleNames:['Alpha','Beta']});
  eq(subject.resolveCredentialClientId(),'','numeric aggregate sentinel must suppress stale and visible client ids');
}
{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:'ALL',selectedClientId:'c2'},{visibleNames:['Beta']});
  eq(subject.resolveCredentialClientId(),'','ALL aggregate sentinel must suppress a uniquely visible client');
}

// An explicit concrete asset selection is authoritative. It must not be replaced by
// stale detail state or by another client name that happens to be visible in the DOM.
{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:'c2',selectedClientId:'c1'},{visibleNames:['Alpha']});
  eq(subject.resolveCredentialClientId(),'c2','explicit asset selection must outrank visible/stale client state');
}

// Before the explicit aggregate selector existed, the resolver intentionally fell
// back to a unique visible client. Preserve that behavior for legacy asset contexts
// where selectedAssetsClientId is absent.
{
  const subject=makeSubject({currentPage:'assets',clients,selectedClientId:'stale'},{visibleNames:['Beta']});
  eq(subject.resolveVisibleClientId(),'c2','unique visible client detection');
  eq(subject.resolveCredentialClientId(),'c2','unique visible client must outrank stale selectedClientId on asset page');
}
{
  const subject=makeSubject({currentPage:'assets',clients,assetClientId:'c1',selectedClientId:'stale'},{visibleNames:[],bodyNames:[]});
  eq(subject.resolveCredentialClientId(),'c1','legacy explicit asset client id remains supported when no visible client resolves');
}

// Outside the account-assets page, client-detail keeps its historical explicit
// selectedClientId behavior; the aggregate hardening must not break that flow.
{
  const subject=makeSubject({currentPage:'client-detail',clients,selectedClientId:'c1'},{assetPage:false,visibleNames:['Beta']});
  eq(subject.resolveCredentialClientId(),'c1','client-detail selectedClientId behavior must remain intact');
}

console.log('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_OK: aggregate=0+ALL-deny; explicit-asset=authoritative; visible-fallback=unique; stale-detail=isolated; client-detail=preserved');
