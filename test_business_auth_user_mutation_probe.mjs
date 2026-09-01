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

const save=extractMethod('saveAuthUser');
const del=extractMethod('deleteAuthUser');
throw new Error('BUSINESS_AUTH_USER_MUTATION_SOURCE_PROBE: '+JSON.stringify({save,delete:del}));
