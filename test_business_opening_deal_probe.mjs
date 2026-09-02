import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_OPENING_DEAL_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_OPENING_DEAL_PROBE_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  if(open<0)throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} opening brace missing`);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){
      if(escaped){escaped=false;continue}
      if(ch==='\\'){escaped=true;continue}
      if(ch===quote)quote='';
      continue;
    }
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;
    else if(ch==='}'){
      depth-=1;
      if(depth===0)return bundle.slice(start,i+1).trim();
      if(depth<0)break;
    }
  }
  throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} closing brace missing`);
}

const names=['saveOpeningDeal','deleteOpeningDeal'];
const sources=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
for(const name of names){
  console.log(`BUSINESS_OPENING_DEAL_PROBE_SOURCE_${name}=`+JSON.stringify(sources[name]));
  try{
    const single=vm.runInNewContext(`({${sources[name]}})`,{Number,String,Object,Array,Math,Set,JSON,Date},{timeout:1000});
    if(typeof single[name]!=='function')throw new Error(`${name} not executable`);
    console.log(`BUSINESS_OPENING_DEAL_PROBE_COMPILE_${name}=OK`);
  }catch(error){
    throw new Error(`BUSINESS_OPENING_DEAL_PROBE_FAILED: ${name} compile: ${error.message}`);
  }
}
console.log('BUSINESS_OPENING_DEAL_PROBE_OK: final-dist methods=saveOpeningDeal+deleteOpeningDeal; execution=compiled-only');
