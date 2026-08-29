import fs from 'node:fs';
import path from 'node:path';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_ANALYTICS_INVENTORY_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_ANALYTICS_INVENTORY_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_ANALYTICS_SOURCE_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,templateDepth=0;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1];
    if(quote){
      if(escaped){escaped=false;continue;}
      if(ch==='\\'){escaped=true;continue;}
      if(quote==='`'&&ch==='$'&&next==='{'){templateDepth+=1;i+=1;continue;}
      if(quote==='`'&&templateDepth>0){if(ch==='{')templateDepth+=1;else if(ch==='}')templateDepth-=1;continue;}
      if(ch===quote)quote='';
      continue;
    }
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue;}
    if(ch==='{')depth+=1;
    else if(ch==='}'){
      depth-=1;
      if(depth===0)return bundle.slice(start,i+1).trim();
    }
  }
  throw new Error(`BUSINESS_ANALYTICS_SOURCE_PROBE_FAILED: ${name} boundary drifted`);
}

const targets=[
  'analyticsMetricsForAccount',
  'aggregateAccountsMetrics',
  'analyticsAllFbAccounts',
  'analyticsAllTkAccounts',
  'analyticsAllClientRows',
  'syncAnalyticsAccountSelection',
  'selectedAnalyticsFbMetrics',
  'selectedAnalyticsTkMetrics',
];
for(const name of targets){
  const source=extractMethod(name);
  console.log(`BUSINESS_ANALYTICS_SOURCE:${name}:${Buffer.from(source,'utf8').toString('base64')}`);
}
throw new Error('BUSINESS_ANALYTICS_SOURCE_PIN_REQUIRED: captured final target method sources; replace probe with executable semantic assertions');
