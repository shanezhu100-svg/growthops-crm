import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AUTH_USER_MUTATION_PROBE_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_AUTH_USER_MUTATION_PROBE_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*((?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_AUTH_USER_MUTATION_PROBE_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const open=tail.indexOf('{');
  for(let cursor=open+1;cursor<tail.length;cursor+=1){
    if(tail[cursor]!=='}')continue;
    const source=tail.slice(0,cursor+1).trim();
    try{
      const parsed=vm.runInNewContext(`({${source}})`,Object.create(null),{timeout:100});
      if(typeof parsed?.[name]==='function')return source;
    }catch{}
  }
  throw new Error(`BUSINESS_AUTH_USER_MUTATION_PROBE_FAILED: ${name} boundary not found`);
}

function summarize(name){
  const source=extractMethod(name);
  const thisRefs=[...new Set([...source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)/g)].map(m=>m[1]))].sort();
  const calls=[...new Set([...source.matchAll(/\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)].map(m=>m[1]))].sort();
  const params=(source.match(new RegExp(`^(?:async\\s+)?${name}\\s*\\(([^)]*)\\)`))?.[1]??'').replace(/\s+/g,' ').trim();
  const features={
    async:/^async\s/.test(source),
    confirm:/\b(?:window\.)?confirm\s*\(/.test(source),
    persist:/\bthis\.persist\s*\(/.test(source),
    audit:/\bthis\.logAudit\s*\(/.test(source),
    splice:/\.splice\s*\(/.test(source),
    push:/\.push\s*\(/.test(source),
    assignment:/\bthis\.[A-Za-z_$][A-Za-z0-9_$]*\s*=/.test(source),
  };
  return `${name}:params=${params||'-'}; refs=${thisRefs.join(',')||'-'}; calls=${calls.join(',')||'-'}; features=${Object.entries(features).filter(([,v])=>v).map(([k])=>k).join(',')||'-'}`;
}

throw new Error('BUSINESS_AUTH_USER_MUTATION_PROBE_RESULT: '+[
  summarize('saveAuthUser'),
  summarize('deleteAuthUser'),
].join(' | '));
