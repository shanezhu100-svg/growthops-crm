import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(\`(?:^|[,\\\\n])\\\\s*(\${name}\\\\([^)]*\\\\)\\\\s*\\\\{)\`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(\`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: \${name} not found\`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(\`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: \${name} parser drifted\`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=[
  '_legacyAlertList','alertList','leadFollowupReminderStage','alertDismissKey',
  'isAlertDismissed','leadStageText',
  'financeReceivableCollectionNodes','financeReceivableCollectionAllocation',
  'filteredLeads','leadStats','leadFollowupClass'
];
const source=Object.fromEntries(names.map(name=>[name,extractMethod(name)]));
if(source._legacyAlertList.includes('LEAD_FOLLOWUP'))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: reminder center still generates lead alerts');
if(!source.alertList.includes('this.$options?.computed?._legacyAlertList'))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: alert wrapper lost computed authority');
if(bundle.includes("typeKey:'LEAD_FOLLOWUP'"))throw new Error('BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: final runtime still ships lead reminder-center alert type');

const subject=vm.runInNewContext(\`({\${names.map(name=>source[name]).join(',')}})\`,{Number,String,Object,Array,Math,Date,JSON,Set,Promise},{timeout:1000});

const dayMap={D4:4,D3:3,D2:2,D1:1,D0:0,DM5:-5};
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
  formatMoney(v,c){return \`\${c||'USD'}:\${Number(v||0)}\`;},
  daysUntil(date){return Object.prototype.hasOwnProperty.call(dayMap,date)?dayMap[date]:9999;},
  addDays(date,n){return \`\${date}:\${n}\`;},
  localDateKey(){return'D0';},
  leadSearch:'',leadPoolFilter:'ACTIVE',leadQuickFilter:'ALL',
});
subject.$options={computed:{_legacyAlertList:subject._legacyAlertList}};

const fail=(label,expected,actual)=>{throw new Error(\`BUSINESS_LEAD_FOLLOWUP_REMINDER_FAILED: \${label}; expected=\${expected}; actual=\${actual}\`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const stage=date=>subject.leadFollowupReminderStage(date);

eq(stage('D4'),null,'outside 3-day window');
eq(stage('D3').reminderIndex,1,'3-day stage index');
eq(stage('D2').reminderIndex,1,'2-day stays in first stage');
eq(stage('D1').reminderIndex,2,'1-day stage index');
eq(stage('D0').reminderIndex,3,'today final stage index');
eq(stage('DM5').reminderIndex,3,'overdue remains final stage');

const lead=(id,stageKey,nextFollowUp,extra={})=>({
  id,company:\`Company-\${id}\`,contact:\`Contact-\${id}\`,contactInfo:\`Info-\${id}\`,
  stage:stageKey,nextFollowUp,owner:\`Owner-\${id}\`,convertedClientId:null,...extra
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

const alerts=subject.alertList();
eq(alerts.filter(a=>a.typeKey==='LEAD_FOLLOWUP').length,0,'reminder center has no lead follow-up alerts');

subject.leadQuickFilter='DUE';
const pageRows=subject.filteredLeads();
eq(pageRows.length,4,'lead page reminder queue matches 3-day reminder window');
eq(pageRows.some(l=>l.id==='d3'),true,'3-day lead appears on lead page queue');
eq(pageRows.some(l=>l.id==='d1'),true,'1-day lead appears on lead page queue');
eq(pageRows.some(l=>l.id==='today'),true,'today lead appears on lead page queue');
eq(pageRows.some(l=>l.id==='late'),true,'overdue lead appears on lead page queue');
eq(pageRows.some(l=>l.id==='future'),false,'4-day lead stays outside lead page queue');
eq(pageRows.some(l=>l.id==='won'),false,'won lead stays outside active queue');
eq(pageRows.some(l=>l.id==='lost'),false,'lost lead stays outside active queue');
eq(pageRows.some(l=>l.id==='converted'),false,'converted lead stays outside active queue');
eq(subject.leadStats().due,4,'lead page reminder card count matches reminder window');
eq(subject.leadFollowupClass(subject.leads.find(l=>l.id==='d3')),'text-amber-600','3-day lead uses warning color');
eq(subject.leadFollowupClass(subject.leads.find(l=>l.id==='today')),'text-rose-600','today lead uses urgent color');
eq(subject.leadFollowupClass(subject.leads.find(l=>l.id==='late')),'text-rose-600','overdue lead uses urgent color');
eq(subject.leadFollowupClass(subject.leads.find(l=>l.id==='future')),'text-slate-700','outside-window lead stays neutral');

console.log('BUSINESS_LEAD_FOLLOWUP_REMINDER_OK: surface=lead-page-only; reminder-center=0; window=3/1/0+overdue; active-only=NEW+CONTACTED+QUALIFIED+PROPOSAL; won+lost+converted=excluded; lead-page=3d-queue+color-coded');
