import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const saveSource=extractMethod('saveReceivable');
const listSource=extractMethod('financeReceivablesForClient');
if(!saveSource.includes("linkedClient?.archived")||!saveSource.includes("归档客户不能新增回款账单")){
  throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: archived-new guard missing from saveReceivable');
}
if(saveSource.indexOf("linkedClient?.archived")>saveSource.indexOf("assertMonthUnlocked(f.settlementMonth,'保存收入项目')")){
  throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: archived guard must run before month mutation gate');
}

const save=vm.runInNewContext(`({${saveSource}})`,{String,Number,Object,Array},{timeout:1000}).saveReceivable;
const list=vm.runInNewContext(`({${listSource}})`,{String,Number,Object,Array},{timeout:1000}).financeReceivablesForClient;

function makeSubject({archived,id=null}){
  const notifications=[];
  let monthChecks=0;
  const client={id:'c1',name:'Archived Client',archived};
  const subject={
    clients:[client],
    financeReceivables:[{id:'old-1',clientId:'c1',settlementMonth:'2026-08',amount:100}],
    receivableForm:{id,ownerType:'CLIENT',clientId:'c1',payerName:'',settlementMonth:'2026-09',incomeType:'OTHER',amount:50,directCost:0},
    normalizeReceivable(value){return {...value};},
    notify(message){notifications.push(message);},
    assertMonthUnlocked(){monthChecks+=1;return false;},
    financeSettlementMonthMatch(){return true;},
  };
  return {subject,client,notifications,get monthChecks(){return monthChecks;}};
}

let t=makeSubject({archived:true,id:null});
save.call(t.subject);
if(JSON.stringify(t.notifications)!==JSON.stringify(['归档客户不能新增回款账单']))throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: new archived receivable was not blocked with expected notice');
if(t.monthChecks!==0)throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: archived new receivable reached mutation path');
if(t.subject.financeReceivables.length!==1)throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: archived guard changed historical receivables');

// Active clients still reach the existing save path.
t=makeSubject({archived:false,id:null});
save.call(t.subject);
if(t.notifications.length!==0||t.monthChecks!==1)throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: active client new receivable path changed');

// Existing receivables for archived clients remain editable/history-preserving.
t=makeSubject({archived:true,id:'old-1'});
save.call(t.subject);
if(t.notifications.length!==0||t.monthChecks!==1)throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: existing archived receivable edit was blocked');
const historical=list.call(t.subject,t.client);
if(historical.length!==1||historical[0].id!=='old-1')throw new Error('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_FAILED: archived client historical receivable visibility changed');

console.log('BUSINESS_ARCHIVED_RECEIVABLE_GUARD_OK: archived-new=blocked; active-new=unchanged; archived-existing=editable+visible; payment-history=untouched');
