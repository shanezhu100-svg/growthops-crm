import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_CLIENT_MODULE_HOME_FAILED: dist/app missing; run canonical build first');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
if(!files.length)throw new Error('BUSINESS_CLIENT_MODULE_HOME_FAILED: no final app-inline JS artifacts');
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');

function extractMethod(name){
  const signature=new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`,'m');
  const match=signature.exec(bundle);
  if(!match)throw new Error(`BUSINESS_CLIENT_MODULE_HOME_FAILED: ${name} not found`);
  const start=match.index+match[0].indexOf(match[1]);
  const tail=bundle.slice(start);
  const defs=[...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if(defs.length<2||defs[0][1]!==name)throw new Error(`BUSINESS_CLIENT_MODULE_HOME_FAILED: ${name} parser drifted`);
  const next=defs[1].index+defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0,next).replace(/,\s*$/,'').trim();
}

const names=['navigateTo','sopAllClientRows','sopAllAccountCount','sopAllConfiguredAccountCount','sopAllTodayTaskCount'];
const methods={};
for(const name of names){
  const context={Number,String,Object,Array,Math,Set,Map,Intl,console,setTimeout:(fn)=>{if(typeof fn==='function')fn();return 1;},clearTimeout:()=>{},window:{scrollTo:()=>{},location:{hash:''}},document:{querySelector:()=>null,getElementById:()=>null}};
  const obj=vm.runInNewContext(`({${extractMethod(name)}})`,context,{timeout:1000});
  methods[name]=obj[name];
}
const call=(name,subject,...args)=>methods[name].call(subject,...args);
const fail=(label,expected,actual)=>{throw new Error(`BUSINESS_CLIENT_MODULE_HOME_FAILED: ${label}; expected=${expected}; actual=${actual}`);};
const eq=(actual,expected,label)=>{if(actual!==expected)fail(label,expected,actual);};
const jsonEq=(actual,expected,label)=>{const a=JSON.stringify(actual),e=JSON.stringify(expected);if(a!==e)fail(label,e,a);};

function makeNavSubject(overrides={}){
  const calls=[];
  const target={
    currentPage:'dashboard',
    clients:[{id:'c1',name:'Alpha'},{id:'c2',name:'Beta'}],
    selectedAssetsClientId:'c1',selectedAdsClientId:'c1',selectedAnalyticsClientId:'c1',selectedSopClientId:'c1',
    canViewPage:()=>true,
    notify:(message)=>calls.push(['notify',message]),
    syncAnalyticsAccountSelection:()=>calls.push(['analytics-sync',target.selectedAnalyticsClientId]),
    syncAdsAccountSelection:()=>calls.push(['ads-sync',target.selectedAdsClientId]),
    syncSopAccountSelection:()=>calls.push(['sop-sync',target.selectedSopClientId]),
    ...overrides,
  };
  const subject=new Proxy(target,{
    get(obj,prop){
      if(prop in obj)return obj[prop];
      if(prop==='$nextTick')return fn=>{if(typeof fn==='function')fn();};
      if(typeof prop==='string'&&/^(sync|close|reset|scroll|ensure|load|refresh|prepare|update|clear)/.test(prop))return (...args)=>calls.push([prop,...args]);
      return undefined;
    },
  });
  return {subject,target,calls};
}

// Module-home navigation must write aggregate sentinel 0 before any concrete-client
// validation/synchronization. Normal navigation must preserve sentinel 0 and only
// repair stale non-zero concrete selections.
{
  const {subject,target}=makeNavSubject();
  call('navigateTo',subject,'assets',true);
  eq(target.selectedAssetsClientId,0,'assets module-home sets aggregate sentinel');
  eq(target.currentPage,'assets','assets module-home navigates to requested page');
}
{
  const {subject,target,calls}=makeNavSubject({selectedAdsClientId:'missing'});
  call('navigateTo',subject,'ads',true);
  eq(target.selectedAdsClientId,0,'ads module-home sentinel survives stale-client validation');
  jsonEq(calls.filter(item=>item[0]==='ads-sync'),[['ads-sync',0]],'ads synchronizer observes aggregate sentinel');
}
{
  const {subject,target,calls}=makeNavSubject({selectedAnalyticsClientId:0});
  call('navigateTo',subject,'analytics',false);
  eq(target.selectedAnalyticsClientId,0,'normal analytics navigation preserves existing aggregate sentinel');
  jsonEq(calls.filter(item=>item[0]==='analytics-sync'),[['analytics-sync',0]],'analytics synchronizer preserves aggregate state');
}
{
  const {subject,target}=makeNavSubject({selectedAssetsClientId:'stale'});
  call('navigateTo',subject,'assets',false);
  eq(target.selectedAssetsClientId,'c1','stale non-zero assets selection falls back to first concrete client');
}
{
  const {subject,target,calls}=makeNavSubject({selectedSopClientId:'c2'});
  call('navigateTo',subject,'sop',true);
  eq(target.selectedSopClientId,0,'SOP module-home sets all-client sentinel');
  jsonEq(calls.filter(item=>item[0]==='sop-sync'),[['sop-sync',0]],'SOP synchronizer observes all-client sentinel');
}
{
  const {subject,target,calls}=makeNavSubject({canViewPage:()=>false,selectedAssetsClientId:'c2'});
  call('navigateTo',subject,'assets',true);
  eq(target.currentPage,'dashboard','denied navigation does not change page');
  eq(target.selectedAssetsClientId,'c2','denied navigation does not mutate client selection');
  eq(calls.filter(item=>item[0]==='notify').length,1,'denied navigation reports one access notification');
}

// SOP all-client computed semantics: FB/TikTok account counts, configured account
// counts, today's task totals, deterministic priority sorting, and aggregate cards.
const today='2026-08-29';
const activeClients=[
  {id:'alpha',name:'Alpha',fbAccounts:[{id:'a1'}],tkAccounts:[{id:'a2'}],sopAccountConfigs:{'FB:a1':{dailyTasks:{[today]:['a','b']}}}},
  {id:'gamma',name:'Gamma',fbAccounts:[{id:'g1'}],tkAccounts:[],sopAccountConfigs:{'FB:g1':{dailyTasks:{[today]:['a','b','c']}}}},
  {id:'beta',name:'Beta',fbAccounts:[{id:'b1'}],tkAccounts:[{id:'b2'}],sopAccountConfigs:{'FB:b1':{dailyTasks:{[today]:['a']}},'TK:b2':{dailyTasks:{[today]:['b']}}}},
];
const rows=call('sopAllClientRows',{activeClients,localDateKey:()=>today});
jsonEq(rows.map(row=>row.client.name),['Gamma','Beta','Alpha'],'SOP all-client rows sort by today tasks then configured count');
const byName=Object.fromEntries(rows.map(row=>[row.client.name,row]));
jsonEq(
  [byName.Alpha.fbAccounts,byName.Alpha.tkAccounts,byName.Alpha.accounts,byName.Alpha.configured,byName.Alpha.todayTasks],
  [1,1,2,1,2],
  'SOP Alpha account/config/task aggregation'
);
jsonEq(
  [byName.Beta.fbAccounts,byName.Beta.tkAccounts,byName.Beta.accounts,byName.Beta.configured,byName.Beta.todayTasks],
  [1,1,2,2,2],
  'SOP Beta account/config/task aggregation'
);
jsonEq(
  [byName.Gamma.fbAccounts,byName.Gamma.tkAccounts,byName.Gamma.accounts,byName.Gamma.configured,byName.Gamma.todayTasks],
  [1,0,1,1,3],
  'SOP Gamma account/config/task aggregation'
);
const aggregateSubject={sopAllClientRows:rows};
eq(call('sopAllAccountCount',aggregateSubject),5,'SOP aggregate account count');
eq(call('sopAllConfiguredAccountCount',aggregateSubject),4,'SOP aggregate configured-account count');
eq(call('sopAllTodayTaskCount',aggregateSubject),7,'SOP aggregate today-task count');

console.log('BUSINESS_CLIENT_MODULE_HOME_OK: navigation=sentinel+fallback+deny; sop=fb+tk+configured+today-task+priority-sort+aggregate-counts');
