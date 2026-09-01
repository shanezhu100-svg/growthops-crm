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
  const source=extractMethod(name);
  const parsed=vm.runInNewContext(`({${source}})`,{Date,Number,String,Object,Array,Math,JSON,Set,Map,Intl,RegExp},{timeout:1000});
  return parsed[name];
}
const saveAuthUser=compile('saveAuthUser');
const deleteAuthUser=compile('deleteAuthUser');

function makeCounters(){return {persist:0,audit:0,notify:0,confirm:0};}
const current={id:'auth-current',name:'Current Admin',username:'current-admin',role:'ADMIN',enabled:true};
const other={id:'auth-existing',name:'Existing User',username:'existing-user',role:'USER',enabled:true};

const saveCounters=makeCounters();
const saveSubject={
  authUsers:[{...current},{...other}],
  userForm:{name:'Synthetic New User',username:'synthetic-new-user',password:'SyntheticPass123!'},
  currentUser:{...current},
  currentPage:'users',
  showUserModal:true,
  canViewPage:()=>true,
  accountUid:()=> 'auth-new',
  roleLabel:value=>String(value??''),
  persist:()=>{saveCounters.persist+=1;},
  logAudit:()=>{saveCounters.audit+=1;},
  notify:()=>{saveCounters.notify+=1;},
};
let saveError='-';
try{saveAuthUser.call(saveSubject);}catch(error){saveError=`${error?.name||'Error'}:${error?.message||String(error)}`;}
const added=saveSubject.authUsers.find(user=>user?.id==='auth-new')||null;

const deleteCounters=makeCounters();
const deleteSubject={
  authUsers:[{...current},{...other}],
  currentUser:{...current},
  askConfirm:()=>{deleteCounters.confirm+=1;return true;},
  persist:()=>{deleteCounters.persist+=1;},
  logAudit:()=>{deleteCounters.audit+=1;},
  notify:()=>{deleteCounters.notify+=1;},
};
let deleteError='-';
try{deleteAuthUser.call(deleteSubject,deleteSubject.authUsers[1]);}catch(error){deleteError=`${error?.name||'Error'}:${error?.message||String(error)}`;}

const addedKeys=added?Object.keys(added).sort().filter(key=>key!=='password').join(','):'-';
const passwordKey=Boolean(added&&Object.prototype.hasOwnProperty.call(added,'password'));
const summary=[
  `save:error=${saveError}; added=${Boolean(added)}; len=${saveSubject.authUsers.length}; keys=${addedKeys}; passwordKey=${passwordKey}; persist=${saveCounters.persist}; audit=${saveCounters.audit}; notify=${saveCounters.notify}; modal=${String(saveSubject.showUserModal)}`,
  `delete:error=${deleteError}; targetRemoved=${!deleteSubject.authUsers.some(user=>user?.id==='auth-existing')}; currentRetained=${deleteSubject.authUsers.some(user=>user?.id==='auth-current')}; len=${deleteSubject.authUsers.length}; confirm=${deleteCounters.confirm}; persist=${deleteCounters.persist}; audit=${deleteCounters.audit}; notify=${deleteCounters.notify}`,
];
throw new Error('BUSINESS_AUTH_USER_MUTATION_PROBE_RESULT: '+summary.join(' | '));
