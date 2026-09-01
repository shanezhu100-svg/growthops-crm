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
const saveAuthUser=compile('saveAuthUser');
const deleteAuthUser=compile('deleteAuthUser');
const roles=['ADMIN','MANAGER','OPS','FINANCE','VIEWER','USER','MEMBER','STAFF'];
const current={id:'auth-current',name:'Current Admin',username:'current-admin',role:'ADMIN',enabled:true};

function saveCase(role){
  const counters={persist:0,audit:0,notify:0};
  const subject={
    authUsers:[{...current}],
    userForm:{id:null,name:'Synthetic New User',username:`synthetic-${role.toLowerCase()}`,password:'SyntheticPass123!',role,enabled:true},
    currentUser:{...current},currentPage:'users',showUserModal:true,
    canViewPage:()=>true,accountUid:()=>`new-${role}`,
    roleLabel:value=>String(value??''),
    persist:()=>{counters.persist+=1;},logAudit:()=>{counters.audit+=1;},notify:()=>{counters.notify+=1;},
  };
  let error='-';
  try{saveAuthUser.call(subject);}catch(exc){error=exc?.name||'Error';}
  const added=subject.authUsers.find(user=>user?.id===`new-${role}`)||subject.authUsers.find(user=>user?.username===`synthetic-${role.toLowerCase()}`)||null;
  return {role,error,added:Boolean(added),len:subject.authUsers.length,keys:added?Object.keys(added).sort().filter(k=>k!=='password'):[],passwordKey:Boolean(added&&Object.hasOwn(added,'password')),persist:counters.persist,audit:counters.audit,notify:counters.notify,modal:subject.showUserModal};
}
function deleteCase(role){
  const counters={persist:0,audit:0,notify:0,confirm:0};
  const target={id:`target-${role}`,name:`Target ${role}`,username:`target-${role.toLowerCase()}`,role,enabled:true};
  const subject={
    authUsers:[{...current},{...target}],currentUser:{...current},
    askConfirm:()=>{counters.confirm+=1;return true;},
    persist:()=>{counters.persist+=1;},logAudit:()=>{counters.audit+=1;},notify:()=>{counters.notify+=1;},
  };
  let error='-';
  try{deleteAuthUser.call(subject,target);}catch(exc){error=exc?.name||'Error';}
  return {role,error,removed:!subject.authUsers.some(user=>user?.id===target.id),currentRetained:subject.authUsers.some(user=>user?.id===current.id),len:subject.authUsers.length,confirm:counters.confirm,persist:counters.persist,audit:counters.audit,notify:counters.notify};
}
const saves=roles.map(saveCase);
const deletes=roles.map(deleteCase);
const compactSave=saves.map(r=>`${r.role}:${r.added?'ADD':'DENY'}/${r.persist}/${r.audit}/${r.notify}/${r.modal?'open':'closed'}${r.added?'/'+r.keys.join('+')+'/pwdKey='+r.passwordKey:''}`).join(',');
const compactDelete=deletes.map(r=>`${r.role}:${r.removed?'DEL':'DENY'}/${r.confirm}/${r.persist}/${r.audit}/${r.notify}`).join(',');
throw new Error(`BUSINESS_AUTH_USER_MUTATION_PROBE_RESULT: save=${compactSave} | delete=${compactDelete}`);
