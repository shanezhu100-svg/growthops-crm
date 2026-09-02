import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_BULK_RECEIVABLE_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function scanBalanced(start,openChar,closeChar){
  if(bundle[start]!==openChar)throw new Error(`BUSINESS_BULK_RECEIVABLE_PROBE_FAILED: expected ${openChar}`);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=start;i<bundle.length;i+=1){
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
    if(ch===openChar)depth+=1;
    else if(ch===closeChar&&--depth===0)return i;
  }
  throw new Error(`BUSINESS_BULK_RECEIVABLE_PROBE_FAILED: unmatched ${openChar}`);
}

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*${name}\\s*\\(`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_BULK_RECEIVABLE_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].lastIndexOf(name);
  const paren=bundle.indexOf('(',start+name.length);
  const parenEnd=scanBalanced(paren,'(',')');
  let open=parenEnd+1;
  while(/\s/.test(bundle[open]||''))open+=1;
  if(bundle[open]!=='{')throw new Error(`BUSINESS_BULK_RECEIVABLE_PROBE_FAILED: ${name} body opening brace missing`);
  const end=scanBalanced(open,'{','}');
  return bundle.slice(start,end+1).trim();
}

for(const name of ['generateReceivablesForPeriod','ensureAutomaticReceivables','createReceivableForClientMonth']){
  console.log(`BUSINESS_BULK_RECEIVABLE_PROBE_${name}=`+extractMethod(name));
}
throw new Error('BUSINESS_BULK_RECEIVABLE_PROBE_COMPLETE');