import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root=process.cwd();
const appDir=path.join(root,'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: final runtime ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const methodNames=['archiveClient','restoreClient','deleteLead'];
const methodSource=methodNames.map(extractMethod).join(',\n');
let methods;
try{methods=vm.runInNewContext(`({${methodSource}})`,Object.create(null),{timeout:1000})}
catch(error){throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: unable to execute final runtime methods: ${error.message}`)}
for(const name of methodNames)if(typeof methods[name]!=='function')throw new Error(`BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: ${name} is not executable`);

const fail=message=>{throw new Error('BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_FAILED: '+message)};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${expected}; actual=${actual}`)};
const makeSubject=extra=>Object.assign({},methods,{persistClientLifecycleBarrier:async function(){return this.persist()}},extra||{});

// Archive is permission-gated and confirmation-gated. Nothing durable may happen
// before the user confirms; confirmed archive preserves the record and changes only
// lifecycle state while persisting/auditing exactly once after ACK.
{
  const client={id:'client-a',name:'Client A',archived:false,status:'ACTIVE',archivedAt:''};
  let confirmConfig=null,confirmAction=null,persisted=0,audited=[],notifications=[];
  const s=makeSubject({
    canArchiveClients:()=>true,
    askConfirm:(config,action)=>{confirmConfig=config;confirmAction=action},
    persist:()=>{persisted+=1},
    logAudit:(action,target)=>audited.push([action,target]),
    notify:message=>notifications.push(message),
  });
  s.archiveClient(client);
  eq(client.archived,false,'archive must not mutate before confirmation');
  eq(client.status,'ACTIVE','archive must not change status before confirmation');
  eq(persisted,0,'archive must not persist before confirmation');
  eq(audited.length,0,'archive must not audit before confirmation');
  eq(confirmConfig?.title,'归档客户','archive confirmation title');
  if(typeof confirmAction!=='function')fail('archive confirmation callback missing');
  await confirmAction();
  eq(client.archived,true,'confirmed archive marks client archived');
  eq(client.status,'PAUSED','confirmed archive pauses client');
  if(!/^\d{4}-\d{2}-\d{2}T/.test(client.archivedAt))fail('confirmed archive must record ISO archivedAt');
  eq(persisted,1,'confirmed archive durable barrier count');
  eq(audited.length,1,'confirmed archive audit count');
  eq(audited[0][0],'归档客户','confirmed archive audit action');
  eq(audited[0][1],'Client A','confirmed archive audit target');
  if(!notifications.some(message=>message.includes('已归档')))fail('confirmed archive success notification missing after ACK');
}
{
  const client={id:'client-denied',name:'Denied',archived:false,status:'ACTIVE'};
  let confirms=0,persisted=0,audited=0,notified='';
  const s=makeSubject({
    canArchiveClients:()=>false,
    askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:message=>{notified=message},
  });
  s.archiveClient(client);
  eq(client.archived,false,'unauthorized archive keeps lifecycle state');
  eq(confirms,0,'unauthorized archive must not open confirmation');
  eq(persisted,0,'unauthorized archive must not persist');
  eq(audited,0,'unauthorized archive must not audit success');
  if(!notified.includes('没有归档客户的权限'))fail('unauthorized archive permission notification missing');
}
{
  let confirms=0;
  const s=makeSubject({canArchiveClients:()=>true,askConfirm:()=>{confirms+=1}});
  s.archiveClient(null);
  s.archiveClient({id:'already',name:'Already',archived:true,status:'PAUSED'});
  eq(confirms,0,'null/already archived client must be archive no-op');
}

// Restore mirrors archive: permission + confirmation first, then exact lifecycle
// reset and one acknowledged/audit write.
{
  const client={id:'client-r',name:'Client R',archived:true,status:'PAUSED',archivedAt:'2026-08-01T00:00:00.000Z'};
  let confirmConfig=null,confirmAction=null,persisted=0,audited=[],notifications=[];
  const s=makeSubject({
    canArchiveClients:()=>true,
    askConfirm:(config,action)=>{confirmConfig=config;confirmAction=action},
    persist:()=>{persisted+=1},
    logAudit:(action,target)=>audited.push([action,target]),
    notify:message=>notifications.push(message),
  });
  s.restoreClient(client);
  eq(client.archived,true,'restore must not mutate before confirmation');
  eq(persisted,0,'restore must not persist before confirmation');
  eq(confirmConfig?.title,'恢复归档客户','restore confirmation title');
  if(typeof confirmAction!=='function')fail('restore confirmation callback missing');
  await confirmAction();
  eq(client.archived,false,'confirmed restore clears archived flag');
  eq(client.archivedAt,'','confirmed restore clears archived timestamp');
  eq(client.status,'ACTIVE','confirmed restore reactivates client');
  eq(persisted,1,'confirmed restore durable barrier count');
  eq(audited.length,1,'confirmed restore audit count');
  eq(audited[0][0],'恢复归档客户','confirmed restore audit action');
  eq(audited[0][1],'Client R','confirmed restore audit target');
  if(!notifications.some(message=>message.includes('已恢复')))fail('confirmed restore success notification missing after ACK');
}
{
  const client={id:'client-r-denied',name:'Denied R',archived:true,status:'PAUSED',archivedAt:'x'};
  let confirms=0,persisted=0,audited=0,notified='';
  const s=makeSubject({
    canArchiveClients:()=>false,askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},logAudit:()=>{audited+=1},notify:message=>{notified=message},
  });
  s.restoreClient(client);
  eq(client.archived,true,'unauthorized restore keeps archived flag');
  eq(client.status,'PAUSED','unauthorized restore keeps paused status');
  eq(confirms,0,'unauthorized restore must not open confirmation');
  eq(persisted,0,'unauthorized restore must not persist');
  eq(audited,0,'unauthorized restore must not audit success');
  if(!notified.includes('没有恢复客户的权限'))fail('unauthorized restore permission notification missing');
}
{
  let confirms=0;
  const s=makeSubject({canArchiveClients:()=>true,askConfirm:()=>{confirms+=1}});
  s.restoreClient(null);
  s.restoreClient({id:'active',name:'Active',archived:false,status:'ACTIVE'});
  eq(confirms,0,'null/active client must be restore no-op');
}

// Lead deletion remains confirmation-gated, ID-scoped, and completes only after ACK.
{
  const target={id:7,company:'Target Lead'};
  const other={id:'8',company:'Other Lead'};
  let confirmConfig=null,confirmAction=null,persisted=0,audited=[],notifications=[];
  const s=makeSubject({
    leads:[{id:'7',company:'Target Lead'},other],
    askConfirm:(config,action)=>{confirmConfig=config;confirmAction=action},
    persist:()=>{persisted+=1},
    logAudit:(action,targetName)=>audited.push([action,targetName]),
    notify:message=>notifications.push(message),
  });
  s.deleteLead(target);
  eq(s.leads.length,2,'lead delete must not mutate before confirmation');
  eq(persisted,0,'lead delete must not persist before confirmation');
  eq(audited.length,0,'lead delete must not audit before confirmation');
  eq(confirmConfig?.title,'删除潜在客户','lead delete confirmation title');
  if(typeof confirmAction!=='function')fail('lead delete confirmation callback missing');
  await confirmAction();
  eq(s.leads.length,1,'confirmed lead delete removes exactly matching id');
  eq(String(s.leads[0].id),'8','confirmed lead delete preserves unrelated lead');
  eq(persisted,1,'confirmed lead delete durable barrier count');
  eq(audited.length,1,'confirmed lead delete audit count');
  eq(audited[0][0],'删除潜在客户','confirmed lead delete audit action');
  eq(audited[0][1],'Target Lead','confirmed lead delete audit target');
  if(!notifications.some(message=>message.includes('已删除')))fail('confirmed lead delete success notification missing after ACK');
}
{
  let confirms=0,persisted=0,audited=0;
  const s=makeSubject({leads:[{id:'1'}],askConfirm:()=>{confirms+=1},persist:()=>{persisted+=1},logAudit:()=>{audited+=1}});
  s.deleteLead(null);
  eq(confirms,0,'null lead delete must be no-op');
  eq(persisted,0,'null lead delete must not persist');
  eq(audited,0,'null lead delete must not audit');
}

console.log('BUSINESS_CLIENT_LIFECYCLE_MUTATIONS_OK: archive=permission+confirmation+pause+durable-ACK; restore=permission+confirmation+active+durable-ACK; lead-delete=confirmation+id-scope+durable-ACK; persist+audit=ACK-pinned');
