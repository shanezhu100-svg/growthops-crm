import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
if(!fs.existsSync(adapterPath))throw new Error('BUSINESS_AUTH_USER_MUTATIONS_FAILED: dist/cloud-adapter.js missing; run canonical build first');
const adapter=fs.readFileSync(adapterPath,'utf8');

function extractAssignment(name){
  const marker=`vm.${name}=`;
  const start=adapter.indexOf(marker);
  if(start<0)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: authoritative ${name} override not found`);
  if(adapter.indexOf(marker,start+marker.length)>=0)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: authoritative ${name} override is not unique`);
  const open=adapter.indexOf('{',start+marker.length);
  if(open<0)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${name} body missing`);
  let depth=0;
  for(let cursor=open;cursor<adapter.length;cursor+=1){
    const ch=adapter[cursor];
    if(ch==='{')depth+=1;
    else if(ch==='}'){
      depth-=1;
      if(depth===0){
        const semi=adapter.indexOf(';',cursor);
        if(semi<0||semi-cursor>3)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${name} terminator drifted`);
        return adapter.slice(start,semi+1).trim();
      }
    }
  }
  throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${name} brace boundary drifted`);
}

const saveSource=extractAssignment('saveAuthUser');
const deleteSource=extractAssignment('deleteAuthUser');
for(const [source,markers,label] of [
  [saveSource,["rpc('crm_upsert_user'",'new TextEncoder().encode(f.password).byteLength>72','await loadUsers()','routeFromHash()'],'saveAuthUser'],
  [deleteSource,[
    'const resolve=()=>Array.isArray(vm.authUsers)&&vm.authUsers.length?',
    'vm.authUsers.find(u=>String(u?.id)===String(user?.id))',
    "vm.currentUser?.role!=='ADMIN'",
    'vm.canDeleteAuthUser(target)',
    "vm.askConfirm({title:'删除系统用户'",
    "rpc('crm_delete_user'",
    'p_user_id:target.id',
    'await loadUsers()',
    "vm.logAudit('删除系统用户'",
    'vm.persist()',
  ],'deleteAuthUser'],
]){
  for(const marker of markers)if(!source.includes(marker))throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${label} authoritative marker missing: ${marker}`);
}
if((deleteSource.match(/vm\.currentUser\?\.role!=='ADMIN'/g)||[]).length<2)throw new Error('BUSINESS_AUTH_USER_MUTATIONS_FAILED: deleteAuthUser must re-check ADMIN authority inside confirmation callback');
if((deleteSource.match(/vm\.canDeleteAuthUser\(target\)/g)||[]).length<2)throw new Error('BUSINESS_AUTH_USER_MUTATIONS_FAILED: deleteAuthUser must re-check delete eligibility inside confirmation callback');

const factorySource=`(function(vm,rpc,loadUsers,routeFromHash,token,TextEncoder){\n${saveSource}\n${deleteSource}\nreturn {saveAuthUser:vm.saveAuthUser,deleteAuthUser:vm.deleteAuthUser};\n})`;
let factory;
try{factory=vm.runInNewContext(factorySource,Object.create(null),{timeout:1000});}
catch(error){throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: unable to compile authoritative overrides: ${error.message}`);}

function equal(actual,expected,label){
  if(actual!==expected)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);
}
function truthy(value,label){if(!value)throw new Error(`BUSINESS_AUTH_USER_MUTATIONS_FAILED: ${label}`);}

function makeRuntime({role='ADMIN',userForm={},savedUser=null,rpcError=null,canDelete=true,confirm=true}={}){
  const calls={rpc:[],loadUsers:0,route:0,audit:[],persist:0,notify:[],confirm:[]};
  let confirmPromise=Promise.resolve();
  const subject={
    currentUser:{id:'admin-current',name:'Current Admin',username:'current-admin',role,enabled:true},
    userForm:{id:null,name:'New User',username:'new-user',password:'0123456789',role:'OPS',enabled:true,...userForm},
    authUsers:[],
    showUserModal:true,
    roleLabel:value=>`ROLE:${value}`,
    canDeleteAuthUser:()=>canDelete,
    logAudit:(...args)=>calls.audit.push(args),
    persist:()=>{calls.persist+=1;return true;},
    notify:message=>calls.notify.push(String(message)),
    askConfirm:(config,callback)=>{
      calls.confirm.push(config);
      if(confirm)confirmPromise=Promise.resolve().then(callback);
    },
  };
  const rpc=async(name,body)=>{
    calls.rpc.push({name,body});
    if(rpcError)throw new Error(rpcError);
    if(name==='crm_upsert_user')return savedUser??{id:body.p_user_id||'user-created',name:body.p_name,username:body.p_username,role:body.p_role,enabled:body.p_enabled};
    if(name==='crm_delete_user')return {ok:true};
    throw new Error(`unexpected RPC ${name}`);
  };
  const loadUsers=async()=>{calls.loadUsers+=1;subject.authUsers=[{id:'fresh-user'}];};
  const routeFromHash=()=>{calls.route+=1;};
  factory(subject,rpc,loadUsers,routeFromHash,'session-token',TextEncoder);
  return {subject,calls,waitConfirm:()=>confirmPromise};
}

// Save deny paths must stop before any authoritative server mutation.
{
  const {subject,calls}=makeRuntime({role:'OPS'});
  await subject.saveAuthUser();
  equal(calls.rpc.length,0,'non-admin save must not call RPC');
  equal(calls.notify.length,1,'non-admin save must notify once');
}
{
  const {subject,calls}=makeRuntime({userForm:{name:'   '}});
  await subject.saveAuthUser();
  equal(calls.rpc.length,0,'blank-name save must not call RPC');
}
{
  const {subject,calls}=makeRuntime({userForm:{password:'short'}});
  await subject.saveAuthUser();
  equal(calls.rpc.length,0,'short new-user password must not call RPC');
}
{
  const {subject,calls}=makeRuntime({userForm:{password:'你'.repeat(25)}});
  await subject.saveAuthUser();
  equal(calls.rpc.length,0,'password above 72 UTF-8 bytes must not call RPC');
  truthy(calls.notify.some(message=>message.includes('72')),'byte-cap rejection must remain user-visible');
}
{
  const {subject,calls}=makeRuntime({userForm:{role:'ROOT'}});
  await subject.saveAuthUser();
  equal(calls.rpc.length,0,'invalid role must not call RPC');
}

// New-user success: trim identity fields, preserve selected role/enabled state, then refresh/audit/persist/route.
{
  const {subject,calls}=makeRuntime({userForm:{name:'  Alice Example  ',username:'  alice  ',password:'0123456789',role:'FINANCE',enabled:false}});
  await subject.saveAuthUser();
  equal(calls.rpc.length,1,'successful new-user save RPC count');
  const call=calls.rpc[0];
  equal(call.name,'crm_upsert_user','successful new-user RPC name');
  equal(call.body.p_token,'session-token','successful new-user token authority');
  equal(call.body.p_user_id,null,'new-user id must be null');
  equal(call.body.p_name,'Alice Example','new-user name must be trimmed');
  equal(call.body.p_username,'alice','new-user username must be trimmed');
  equal(call.body.p_password,'0123456789','new-user password must be passed only to server RPC');
  equal(call.body.p_role,'FINANCE','new-user role');
  equal(call.body.p_enabled,false,'new-user enabled flag');
  equal(calls.loadUsers,1,'successful new-user save must reload users');
  equal(subject.showUserModal,false,'successful new-user save must close modal');
  equal(calls.audit.length,1,'successful new-user save audit count');
  equal(calls.persist,1,'successful new-user save persist count');
  equal(calls.route,1,'successful new-user save route refresh count');
  equal(calls.notify.at(-1),'用户权限已保存到服务器','successful new-user notice');
}

// Editing the signed-in account may keep password blank and must refresh currentUser from server result.
{
  const saved={id:'admin-current',name:'Renamed Admin',username:'current-admin',role:'ADMIN',enabled:true};
  const {subject,calls}=makeRuntime({userForm:{id:'admin-current',name:' Renamed Admin ',username:' current-admin ',password:'',role:'ADMIN'},savedUser:saved});
  await subject.saveAuthUser();
  equal(calls.rpc.length,1,'successful self-edit RPC count');
  equal(calls.rpc[0].body.p_password,'','blank edit password must preserve server-side password semantics');
  equal(subject.currentUser.name,'Renamed Admin','self edit must refresh currentUser from saved server row');
  equal(calls.loadUsers,1,'self edit must reload users');
}

// Save server failures must not claim success or mutate post-success state.
{
  const {subject,calls}=makeRuntime({rpcError:'UPSERT_FAILED'});
  await subject.saveAuthUser();
  equal(calls.rpc.length,1,'failed save RPC count');
  equal(calls.loadUsers,0,'failed save must not reload users');
  equal(calls.audit.length,0,'failed save must not audit success');
  equal(calls.persist,0,'failed save must not persist success');
  equal(subject.showUserModal,true,'failed save must keep modal open');
  equal(calls.notify.at(-1),'UPSERT_FAILED','failed save must surface sanitized adapter error');
}

// Delete deny paths must fail before confirmation/RPC.
{
  const {subject,calls}=makeRuntime({role:'OPS'});
  subject.deleteAuthUser({id:'target',name:'Target',role:'OPS'});
  equal(calls.confirm.length,0,'non-admin delete must not confirm');
  equal(calls.rpc.length,0,'non-admin delete must not call RPC');
}
{
  const {subject,calls}=makeRuntime({canDelete:false});
  subject.deleteAuthUser({id:'admin-current',name:'Current Admin',role:'ADMIN'});
  equal(calls.confirm.length,0,'self delete denial must occur before confirmation');
  equal(calls.rpc.length,0,'self delete denial must occur before RPC');
  truthy(calls.notify.at(-1).includes('当前正在登录'),'self delete must use explicit denial message');
}
{
  const {subject,calls}=makeRuntime({canDelete:false});
  subject.deleteAuthUser({id:'other-admin',name:'Other Admin',role:'ADMIN'});
  equal(calls.confirm.length,0,'last-enabled-admin denial must occur before confirmation');
  equal(calls.rpc.length,0,'last-enabled-admin denial must occur before RPC');
  truthy(calls.notify.at(-1).includes('至少需要保留一个'),'last-enabled-admin denial message');
}

// Cancellation must stop before the server delete; confirmed delete executes the exact server phase chain.
{
  const {subject,calls,waitConfirm}=makeRuntime({confirm:false});
  subject.deleteAuthUser({id:'target-cancel',name:'Target Cancel',role:'OPS'});
  await waitConfirm();
  equal(calls.confirm.length,1,'cancel path confirmation count');
  equal(calls.rpc.length,0,'cancelled delete must not call RPC');
  equal(calls.audit.length,0,'cancelled delete must not audit');
  equal(calls.persist,0,'cancelled delete must not persist');
}
{
  const {subject,calls,waitConfirm}=makeRuntime();
  const target={id:'target-delete',name:'Target Delete',role:'OPS'};
  subject.deleteAuthUser(target);
  await waitConfirm();
  equal(calls.confirm.length,1,'confirmed delete confirmation count');
  equal(calls.confirm[0].title,'删除系统用户','confirmed delete dialog title');
  equal(calls.rpc.length,1,'confirmed delete RPC count');
  equal(calls.rpc[0].name,'crm_delete_user','confirmed delete RPC name');
  equal(calls.rpc[0].body.p_token,'session-token','confirmed delete token authority');
  equal(calls.rpc[0].body.p_user_id,'target-delete','confirmed delete target id');
  equal(calls.loadUsers,1,'confirmed delete must reload users');
  equal(calls.audit.length,1,'confirmed delete audit count');
  equal(calls.persist,1,'confirmed delete persist count');
  equal(calls.notify.at(-1),'用户已从服务器删除','confirmed delete success notice');
}
{
  const {subject,calls,waitConfirm}=makeRuntime({rpcError:'DELETE_FAILED'});
  subject.deleteAuthUser({id:'target-fail',name:'Target Fail',role:'OPS'});
  await waitConfirm();
  equal(calls.rpc.length,1,'failed delete RPC count');
  equal(calls.loadUsers,0,'failed delete must not reload users');
  equal(calls.audit.length,0,'failed delete must not audit success');
  equal(calls.persist,0,'failed delete must not persist success');
  equal(calls.notify.at(-1),'DELETE_FAILED','failed delete must surface adapter error');
}

console.log('BUSINESS_AUTH_USER_MUTATIONS_OK: authority=final-cloud-adapter; save=admin+validation+rpc+refresh+self-edit+failure; delete=admin+live-user+can-delete-recheck+confirmation+rpc+refresh+failure; persist+audit=success-only');
