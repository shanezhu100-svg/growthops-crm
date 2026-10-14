import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  '_legacyAlertList','alertList','leadFollowupReminderStage','alertDismissKey',
  'isAlertDismissed','leadStageText','alertIgnoreFollowupText',
  'handleAlertComplete','noticeText','activeDismissedAlertCount',
  'financeReceivableCollectionNodes','financeReceivableCollectionAllocation'
];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
if(!source._legacyAlertList.includes("typeKey:'LEAD_FOLLOWUP'"))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: final alert generator missing lead reminders');
if(!source.alertList.includes('this.$options?.computed?._legacyAlertList'))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: alert wrapper lost computed authority');
if(!source.activeDismissedAlertCount.includes('LEAD_FOLLOWUP-${lead.id}'))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: dismissed-count authority missing lead keys');

const subject=vm.runInNewContext(`({${names.map(name=>source[name]).join(',')}})`,{Number,String,Object,Array,Math,Date,JSON,Set,Promise},{timeout:1000});

const dayMap={D4:4,D3:3,D2:2,D1:1,D0:0,DM5:-5};
let openedLead=null,navigated='',notice='';
Object.assign(subject,{
  clients:[],financeReceivables:[],standaloneAlerts:[],dismissedAlerts:[],leads:[],
  pushDueAlert(){},pushRechargeAlert(){},
  financeReceivableUnpaid(){return 0;},
  financeReceivableClientName(){return'';},
  financeReceivablePaid(){return 0;},
  financeIncomeTypeText(){return'';},
  autoDueReminderStage(){return null;},
  contractDueReminderStage(){return null;},
  alertTypeName(k){return k;},
  formatMoney(v,c){return `${c||'USD'}:${Number(v||0)}`;},
  daysUntil(date){return Object.prototype.hasOwnProperty.call(dayMap,date)?dayMap[date]:9999;},
  addDays(date,n){return `${date}:${n}`;},
  followupLabel(date){const d=this.daysUntil(date);if(d<0)return`已逾期 ${Math.abs(d)} 天`;if(d===0)return'今天跟进';if(d===1)return'明天跟进';return`${d} 天后跟进`;},
  notify(msg){notice=String(msg||'');},
  navigateTo(page){navigated=page;},
  $nextTick(fn){fn();},
  openLeadModal(lead){openedLead=lead;},
  openRenewalModal(){throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: lead alert fell through to renewal');},
});
subject.$options={computed:{_legacyAlertList:subject._legacyAlertList}};

const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const stage=date=>subject.leadFollowupReminderStage(date);

eq(stage('D4'),null,'outside 3-day window');
eq(stage('D3').reminderIndex,1,'3-day stage index');
eq(stage('D2').reminderIndex,1,'2-day stays in first stage');
eq(stage('D1').reminderIndex,2,'1-day stage index');
eq(stage('D0').reminderIndex,3,'today final stage index');
eq(stage('DM5').reminderIndex,3,'overdue remains final stage');
eq(stage('DM5').reminderDaysBefore,0,'overdue final stage remains today/overdue authority');

const lead=(id,stageKey,nextFollowUp,extra={})=>({
  id,company:`Company-${id}`,contact:`Contact-${id}`,contactInfo:`Info-${id}`,
  stage:stageKey,nextFollowUp,owner:`Owner-${id}`,convertedClientId:null,...extra
});
subject.leads=[
  lead('d3','NEW','D3'),
  lead('d1','CONTACTED','D1'),
  lead('today','QUALIFIED','D0'),
  lead('late','PROPOSAL','DM5'),
  lead('future','NEW','D4'),
  lead('won','WON','D0'),
  lead('lost','LOST','D0'),
  lead('converted','PROPOSAL','D0',{convertedClientId:'client-1'}),
  lead('none','NEW',''),
];

let alerts=subject.alertList();
eq(alerts.filter(a=>a.typeKey==='LEAD_FOLLOWUP').length,4,'only active due/near-due leads remind');
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-future'),false,'future lead outside window excluded');
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-won'),false,'won lead excluded');
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-lost'),false,'lost lead excluded');
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-converted'),false,'converted lead excluded');

const lateAlert=alerts.find(a=>a.id==='LEAD_FOLLOWUP-late');
eq(lateAlert.daysLeft,-5,'overdue lead days preserved');
eq(lateAlert.reminderIndex,3,'overdue lead uses final reminder stage');
eq(lateAlert.cost,'报价 / 方案中 · Owner-late','lead card stage/owner metadata');
eq(lateAlert.target,'Contact-late · Info-late','lead card contact metadata');

const d3Alert=alerts.find(a=>a.id==='LEAD_FOLLOWUP-d3');
subject.dismissedAlerts=[{key:subject.alertDismissKey(d3Alert)}];
alerts=subject.alertList();
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-d3'),false,'dismissed current lead stage hidden');
eq(subject.activeDismissedAlertCount(),1,'active dismissed lead counted');
subject.leads.find(l=>l.id==='d3').nextFollowUp='D1';
alerts=subject.alertList();
eq(alerts.some(a=>a.id==='LEAD_FOLLOWUP-d3'),true,'rescheduled lead creates new reminder key');

eq(subject.alertIgnoreFollowupText({typeKey:'LEAD_FOLLOWUP',reminderIndex:1,reminderTotal:3}).includes('1 天'),true,'early-stage ignore copy mentions next stage');
eq(subject.alertIgnoreFollowupText({typeKey:'LEAD_FOLLOWUP',reminderIndex:2,reminderTotal:3}).includes('当天'),true,'one-day ignore copy mentions today');
eq(subject.alertIgnoreFollowupText({typeKey:'LEAD_FOLLOWUP',reminderIndex:3,reminderTotal:3}).includes('修改下次跟进日期'),true,'final ignore copy explains new cycle');

const openTarget=subject.leads.find(l=>l.id==='today');
openedLead=null;navigated='';
subject.handleAlertComplete({typeKey:'LEAD_FOLLOWUP',leadId:'today'});
eq(navigated,'leads','lead alert navigates to lead pool');
eq(openedLead,openTarget,'lead alert opens matching lead');
eq(subject.leadPoolFilter,'ACTIVE','lead alert selects active pool');
eq(subject.leadQuickFilter,'ALL','lead alert resets quick filter');

notice='';
subject.handleAlertComplete({typeKey:'LEAD_FOLLOWUP',leadId:'missing'});
eq(notice,'潜在客户已不存在或已删除','stale lead alert fails safely');

const leadNotice=subject.noticeText(lateAlert);
eq(leadNotice.includes('【潜客跟进提醒】Company-late'),true,'lead notice title/company');
eq(leadNotice.includes('已逾期 5 天'),true,'lead notice overdue wording');
eq(leadNotice.includes('请及时跟进并更新下一次跟进日期'),true,'lead notice action wording');

console.log('BUSINESS_LEAD_FOLLOWUP_REMINDER_OK: window=3/1/0+overdue; active-only=NEW+CONTACTED+QUALIFIED+PROPOSAL; won+lost+converted=excluded; dismissal=stage-aware; reschedule=new-key; action=opens-lead; copy=followup-semantic');
