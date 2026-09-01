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
function compile(name){
  const parsed=vm.runInNewContext(`({${extractMethod(name)}})`,{Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp},{timeout:1000});
  return parsed[name];
}
const deleteAuthUser=compile('deleteAuthUser');

const baseCurrent={id:'auth-current',name:'Current Admin',username:'current-admin',role:'ADMIN',enabled:true};
function deleteCase({label,role='OPS',enabled=true,self=false,confirm=true}){
  const counters={persist:0,audit:0,notify:0,confirm:0};
  const current={...baseCurrent};
  const target=self
    ? {...current,enabled}
    : {id:`target-${label}`,name:`Target ${label}`,username:`target-${label}`,role,enabled};
  const subject={
    authUsers:self?[{...target}]:[{...current},{...target}],
    currentUser:{...current},
    askConfirm:()=>{counters.confirm+=1;return confirm;},
    persist:()=>{counters.persist+=1;},
    logAudit:()=>{counters.audit+=1;},
    notify:()=>{counters.notify+=1;},
  };
  let error='-';
  try{deleteAuthUser.call(subject,target);}catch(exc){error=exc?.name||'Error';}
  return {
    label,error,removed:!subject.authUsers.some(user=>user?.id===target.id),
    currentRetained:subject.authUsers.some(user=>user?.id===current.id),
    len:subject.authUsers.length,...counters,
  };
}

const cases=[
  deleteCase({label:'ops-enabled',role:'OPS',enabled:true}),
  deleteCase({label:'ops-disabled',role:'OPS',enabled:false}),
  deleteCase({label:'finance-disabled',role:'FINANCE',enabled:false}),
  deleteCase({label:'admin-disabled',role:'ADMIN',enabled:false}),
  deleteCase({label:'self-disabled',role:'ADMIN',enabled:false,self:true}),
  deleteCase({label:'ops-disabled-cancel',role:'OPS',enabled:false,confirm:false}),
];
const compact=cases.map(r=>`${r.label}:${r.removed?'DEL':'DENY'}/current=${r.currentRetained?'keep':'gone'}/len=${r.len}/confirm=${r.confirm}/persist=${r.persist}/audit=${r.audit}/notify=${r.notify}/error=${r.error}`).join(',');
throw new Error(`BUSINESS_AUTH_USER_MUTATION_PROBE_RESULT: delete=${compact}`);
