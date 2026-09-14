import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: no app-inline JS');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const open=bundle.indexOf('{',start);
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=open;i<bundle.length;i+=1){
    const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}
    if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}
    if(ch==='{')depth+=1;else if(ch==='}'&&--depth===0)return bundle.slice(start,i+1).trim();
  }
  throw new Error(`BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: ${name} closing brace missing`);
}

function compileMethod(name){
  const source=extractMethod(name);
  const compiled=vm.runInNewContext(`({${source}})`,{Number,String,Object,Array,Math,Set,JSON,Date,Promise,Error},{timeout:1000});
  if(typeof compiled[name]!=='function')throw new Error(`BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: ${name} not executable`);
  return {source,fn:compiled[name]};
}

const fail=m=>{throw new Error('BUSINESS_CONTRACT_REMINDER_WINDOW_FAILED: '+m)};
const eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${JSON.stringify(b)}; actual=${JSON.stringify(a)}`)};
const ok=(v,m)=>{if(!v)fail(m)};

const defaultForm=compileMethod('defaultForm').fn;
const normalizeClient=compileMethod('normalizeClient').fn;
const autoDueReminderStage=compileMethod('autoDueReminderStage').fn;
const contractDueReminderStage=compileMethod('contractDueReminderStage').fn;
const pushDueAlert=compileMethod('pushDueAlert').fn;
const alertIgnoreFollowupText=compileMethod('alertIgnoreFollowupText').fn;
const restoreSource=extractMethod('restoreDismissedAlerts');
const deleteSource=extractMethod('deleteAlert');

{
  const ctx={emptyFbAccount(){return{}},emptyTkAccount(){return{}},emptyNetworkEnvironment(){return{}}};
  const form=defaultForm.call(ctx);
  eq(form.renewalAlertDay,25,'payment due day default preserved');
  eq(form.contractReminderDays,25,'contract reminder default is 25 days');
  ok(form.collectionPlan&&form.collectionPlan.mode==='MONTHLY','collection plan remains independent');
}

{
  const client={id:'c1',renewalAlertDay:15,billingMode:'FULL_MONTH',networkEnvironments:[],fbAccounts:[],tkAccounts:[],googleAccounts:[],instagramAccounts:[],adCampaigns:[],sopSteps:[],sopAccountConfigs:{}};
  const ctx={syncLegacyAccountFields(c){return c},syncLegacyNetworkFields(c){return c},accountUid(prefix){return `${prefix}-x`}};
  const normalized=normalizeClient.call(ctx,client);
  eq(normalized.renewalAlertDay,15,'existing payment due day must not become renewal lead time');
  eq(normalized.contractReminderDays,25,'legacy client gets independent 25-day renewal default');
}

function stageAt(days,lead=25){
  const ctx={daysUntil(){return days},addDays(date,n){return `${date}:${n}`}};
  return contractDueReminderStage.call(ctx,{contractReminderDays:lead},'2026-09-30');
}
eq(stageAt(26),null,'contract outside 25-day window hidden');
let s=stageAt(25);eq(s.reminderIndex,1,'contract enters lead stage at N days');eq(s.reminderTotal,4,'contract has four stages');eq(s.reminderDaysBefore,25,'lead stage records configured window');
s=stageAt(8);eq(s.reminderIndex,1,'contract remains visible continuously before 7-day escalation');
s=stageAt(7);eq(s.reminderIndex,2,'contract escalates at 7 days');eq(s.reminderDaysBefore,7,'7-day escalation marker');
s=stageAt(3);eq(s.reminderIndex,3,'contract escalates at 3 days');
s=stageAt(1);eq(s.reminderIndex,4,'contract escalates at 1 day');
s=stageAt(-5);eq(s.reminderIndex,4,'contract overdue remains in final stage through grace window');
eq(stageAt(-31),null,'contract older than 30 days leaves active window');
s=stageAt(30,30);eq(s.reminderIndex,1,'custom renewal lead days honored');
s=stageAt(180,999);eq(s.reminderDaysBefore,180,'renewal lead is capped at 180 days');

{
  const ctx={daysUntil(){return 8},addDays(){return'2026-09-23'}};
  eq(autoDueReminderStage.call(ctx,'2026-09-30'),null,'generic IP/receivable rule remains hidden at 8 days');
  ctx.daysUntil=()=>7;
  const generic=autoDueReminderStage.call(ctx,'2026-09-30');
  eq(generic.reminderIndex,1,'generic rule still starts at 7 days');
  eq(generic.reminderTotal,3,'generic rule remains 7/3/1 with three stages');
}

{
  const list=[],client={id:'c1',name:'Client',contractReminderDays:25};
  const ctx={daysUntil(){return 16},contractDueReminderStage(c,date){return contractDueReminderStage.call({daysUntil:()=>16,addDays:(d,n)=>`${d}:${n}`},c,date)},autoDueReminderStage(){fail('contract must not call generic stage')}};
  pushDueAlert.call(ctx,list,client,'CONTRACT','2026-09-30','服务合同到期','','Service');
  eq(list.length,1,'contract visible at 16 days inside 25-day window');
  eq(list[0].reminderIndex,1,'contract card uses lead stage');
  eq(list[0].reminderWindowDays,25,'contract card carries renewal window metadata');
}

{
  const list=[],client={id:'c1',name:'Client'};
  const ctx={daysUntil(){return 8},contractDueReminderStage(){fail('IP must not call contract stage')},autoDueReminderStage(){return null}};
  pushDueAlert.call(ctx,list,client,'IP','2026-09-30','静态 IP / 节点','','US node','net-1');
  eq(list.length,0,'IP remains outside generic 7-day window at 8 days');
}

ok(alertIgnoreFollowupText.call({}, {typeKey:'CONTRACT',reminderIndex:1,reminderTotal:4}).includes('7 天、3 天和 1 天'),'contract lead-stage dismissal explains later escalations');
ok(alertIgnoreFollowupText.call({}, {typeKey:'CONTRACT',reminderIndex:2,reminderTotal:4}).includes('3 天和 1 天'),'contract 7-day dismissal explains 3/1 followups');
ok(alertIgnoreFollowupText.call({}, {typeKey:'CONTRACT',reminderIndex:3,reminderTotal:4}).includes('1 天'),'contract 3-day dismissal explains 1-day followup');
ok(alertIgnoreFollowupText.call({}, {typeKey:'CONTRACT',reminderIndex:4,reminderTotal:4}).includes('最后阶段'),'contract final-stage dismissal is truthful');
ok(restoreSource.includes('this.contractDueReminderStage(c,c.endDate)'),'restore ignored contract reminders must use contract stage authority');
ok(deleteSource.includes('>=Number(item?.reminderTotal||3)'),'delete/ignore success messaging must use dynamic final stage');

console.log('BUSINESS_CONTRACT_REMINDER_WINDOW_OK: payment-due=independent; legacy-contract=25-day-default; contract=N/7/3/1-continuous; ip+receivable=7/3/1-unchanged; dismissal+restore=stage-aware');
