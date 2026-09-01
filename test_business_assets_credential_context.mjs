import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const securityPath=path.join(process.cwd(),'dist','cloud-security-hotfix.js');
if(!fs.existsSync(securityPath))throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: dist/cloud-security-hotfix.js missing; run canonical build first');
const source=fs.readFileSync(securityPath,'utf8');

function extractArrowConst(name){
  const marker=`const ${name}=()=>{`;
  const start=source.indexOf(marker);
  if(start<0)throw new Error(`BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: final ${name} implementation not found`);
  const open=source.indexOf('{',start+marker.length-1);
  let depth=0;
  for(let i=open;i<source.length;i+=1){
    const ch=source[i];
    if(ch==='{')depth+=1;
    else if(ch==='}'){
      depth-=1;
      if(depth===0){
        const semi=source.indexOf(';',i);
        if(semi<0||semi-i>3)throw new Error(`BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: ${name} terminator drifted`);
        return source.slice(start,semi+1).trim();
      }
    }
  }
  throw new Error(`BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: ${name} brace boundary drifted`);
}

const visibleSource=extractArrowConst('resolveVisibleClientId');
const credentialSource=extractArrowConst('resolveCredentialClientId');
if(!credentialSource.includes('const explicitAssetsClientId=vm.selectedAssetsClientId;'))throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: aggregate asset sentinel hardening missing from final resolver');
if(!credentialSource.includes("vm.currentPage==='client-detail'||vm.currentPage==='client-form'"))throw new Error('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_FAILED: explicit client-form/detail precedence missing from final resolver');

const factorySource=`(function(vm,document,window,cleanText,isAccountAssetPage){\n${visibleSource}\n${credentialSource}\nreturn {resolveVisibleClientId,resolveCredentialClientId};\n})`;
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

{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:0,selectedClientId:'c1'},{visibleNames:['Alpha','Beta']});
  eq(subject.resolveCredentialClientId(),'','numeric aggregate sentinel must suppress stale and visible client ids');
}
{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:'ALL',selectedClientId:'c2'},{visibleNames:['Beta']});
  eq(subject.resolveCredentialClientId(),'','ALL aggregate sentinel must suppress a uniquely visible client');
}
{
  const subject=makeSubject({currentPage:'client-form',clients,selectedAssetsClientId:0,selectedClientId:'c1'},{visibleNames:['Alpha','Beta'],assetPage:true});
  eq(subject.resolveCredentialClientId(),'c1','client-form selectedClientId must outrank stale aggregate asset sentinel');
}
{
  const subject=makeSubject({currentPage:'client-detail',clients,selectedAssetsClientId:'ALL',selectedClientId:'c2'},{visibleNames:['Alpha','Beta'],assetPage:true});
  eq(subject.resolveCredentialClientId(),'c2','client-detail selectedClientId must outrank stale aggregate asset sentinel');
}
{
  const subject=makeSubject({currentPage:'assets',clients,selectedAssetsClientId:'c2',selectedClientId:'c1'},{visibleNames:['Alpha']});
  eq(subject.resolveCredentialClientId(),'c2','explicit asset selection must outrank visible/stale client state');
}
{
  const subject=makeSubject({currentPage:'assets',clients,selectedClientId:'stale'},{visibleNames:['Beta']});
  eq(subject.resolveVisibleClientId(),'c2','unique visible client detection');
  eq(subject.resolveCredentialClientId(),'c2','unique visible client must outrank stale selectedClientId on asset page');
}
{
  const subject=makeSubject({currentPage:'assets',clients,assetClientId:'c1',selectedClientId:'stale'},{visibleNames:[],bodyNames:[]});
  eq(subject.resolveCredentialClientId(),'c1','legacy explicit asset client id remains supported when no visible client resolves');
}
{
  const subject=makeSubject({currentPage:'client-detail',clients,selectedClientId:'c1'},{assetPage:false,visibleNames:['Beta']});
  eq(subject.resolveCredentialClientId(),'c1','client-detail selectedClientId behavior must remain intact');
}

console.log('BUSINESS_ASSETS_CREDENTIAL_CONTEXT_OK: assets-aggregate=0+ALL-deny; client-form+detail=explicit-id-before-body-heuristic; explicit-asset=authoritative; visible-fallback=unique; stale-detail=isolated');
await import('./test_business_client_tiktok_save.mjs');
await import('./test_business_analytics_inventory.mjs');
