import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adapterPath=path.join(process.cwd(),'dist','cloud-adapter.js');
const source=fs.readFileSync(adapterPath,'utf8');
for(const marker of [
  'const auditBefore=new Set(Array.isArray(vm.auditLogs)?vm.auditLogs:[])',
  'const logoutAuditRows=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!auditBefore.has(row)):[]',
  'const rollbackRows=new Set(logoutAuditRows);vm.auditLogs=vm.auditLogs.filter(row=>!rollbackRows.has(row))',
])if(!source.includes(marker))throw new Error(`BUSINESS_LOGOUT_AUDIT_TRUTHFULNESS_FAILED: final adapter marker missing: ${marker}`);

const start=source.indexOf('vm.logout=async()=>{');
const end=source.indexOf('\n',start);
if(start<0||end<0)throw new Error('BUSINESS_LOGOUT_AUDIT_TRUTHFULNESS_FAILED: final logout function missing');
const logoutSource=source.slice(start,end).trim();
const fail=message=>{throw new Error('BUSINESS_LOGOUT_AUDIT_TRUTHFULNESS_FAILED: '+message);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(`${label}; expected=${JSON.stringify(expected)}; actual=${JSON.stringify(actual)}`);};
const ok=(value,label)=>{if(!value)fail(label);};

const existing={action:'已有合法审计',detail:'before'};
const subject={
  currentUser:{id:'admin',name:'Admin'},
  auditLogs:[existing],
  currentPage:'system',loginForm:{username:'admin',password:'form'},
  logAudit(action,detail){this.auditLogs.push({action,detail,attempt:true});},
  notify(){},
};
let failSave=true;
let savedRows=[];
let logoutRpcCount=0;
const asyncUnrelated={action:'等待期间合法审计',detail:'concurrent'};
const context={
  vm:subject,token:'cookie',revision:1,SESSION_MARKER:'cookie',
  flushSave:async()=>{
    if(failSave){subject.auditLogs.push(asyncUnrelated);throw new Error('SYNTHETIC_SAVE_FAILED');}
    savedRows=[...subject.auditLogs];
  },
  rpc:async name=>{if(name==='crm_logout')logoutRpcCount+=1;return {};},
  emptyState(){subject.auditLogs=[];},
};
vm.runInNewContext(logoutSource,context,{timeout:1000});

// Cancelled logout: remove only the exit audit created by this attempt.
await subject.logout();
eq(subject.currentUser?.id,'admin','cancelled logout keeps active session');
eq(logoutRpcCount,0,'cancelled logout does not revoke server session');
eq(subject.auditLogs.filter(row=>row?.action==='退出系统').length,0,'cancelled logout removes false exit audit');
ok(subject.auditLogs.includes(existing),'pre-existing audit row survives rollback');
ok(subject.auditLogs.includes(asyncUnrelated),'unrelated audit appended while save awaited survives rollback');
eq(subject.auditLogs.length,2,'rollback removes only attempt-scoped exit audit');

// Successful retry: exactly one real exit audit is present in the acknowledged save.
failSave=false;
await subject.logout();
eq(logoutRpcCount,1,'successful retry revokes server session once');
eq(savedRows.filter(row=>row?.action==='退出系统').length,1,'successful retry saves exactly one exit audit');
ok(savedRows.includes(existing),'successful retry retains pre-existing audit');
ok(savedRows.includes(asyncUnrelated),'successful retry retains unrelated audit');
eq(subject.currentUser,null,'successful retry completes local logout');

console.log('BUSINESS_LOGOUT_AUDIT_TRUTHFULNESS_OK: authority=final-cloud-adapter; cancelled-logout=false-exit-audit-rolled-back; concurrent-unrelated-audit=preserved; retry-success=single-exit-audit');
