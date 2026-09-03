import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
function scanBalanced(start,openChar,closeChar){
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=start;i<bundle.length;i+=1){const ch=bundle[i],next=bundle[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}
    if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}if(ch===openChar)depth+=1;else if(ch===closeChar&&--depth===0)return i;
  }throw new Error(`BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: unmatched ${openChar}`);
}
function extractMethod(name){
  const m=new RegExp(`(?:^|[,\\n])\\s*${name}\\s*\\(`,'m').exec(bundle);if(!m)throw new Error(`BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: ${name} missing`);
  const start=m.index+m[0].lastIndexOf(name),paren=bundle.indexOf('(',start+name.length),parenEnd=scanBalanced(paren,'(',')');let open=parenEnd+1;while(/\s/.test(bundle[open]||''))open+=1;
  if(bundle[open]!=='{')throw new Error(`BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: ${name} body missing`);const end=scanBalanced(open,'{','}');return bundle.slice(start,end+1).trim();
}
const names=['saveExternalAsset','deleteExternalAsset','saveMediaTool','deleteMediaTool','saveReminderType','deleteReminderType'];
const shipped=vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`,Object.create(null),{timeout:1000});
for(const name of names)if(typeof shipped[name]!=='function')throw new Error(`BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: ${name} not executable`);
const fail=m=>{throw new Error('BUSINESS_RESOURCE_CATALOG_MUTATIONS_FAILED: '+m)},eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${b}; actual=${a}`)},ok=(v,m)=>{if(!v)fail(m)};

function counters(){return {persist:0,audit:0,notify:[],confirm:0,confirmCb:null};}
function wire(o,c){o.persist=()=>{c.persist+=1};o.logAudit=(...args)=>{c.audit+=1;c.lastAudit=args};o.notify=m=>c.notify.push(String(m));o.askConfirm=(_opts,cb)=>{c.confirm+=1;c.confirmCb=cb};return o;}

// External assets: an edit ID is compare-and-set. A stale edit must never turn
// into a new account, and deletes must resolve the live account both before and
// after the user confirmation boundary.
{
  const c=counters(),client={id:'c1',name:'Client',googleAccounts:[],instagramAccounts:[]};
  const o=wire({canManageAssets:()=>true,clients:[client],selectedAssetsClientId:'c1',externalAssetType:'GOOGLE',externalAssetForm:{id:'gone',accountName:'Old',loginAccount:'x',note:''},defaultExternalAssetForm:()=>({}),accountUid:()=> 'generated',showExternalAssetModal:true},c);
  shipped.saveExternalAsset.call(o);
  eq(client.googleAccounts.length,0,'stale external-asset edit must not create a replacement row');eq(c.persist,0,'stale external-asset edit must not persist');eq(c.audit,0,'stale external-asset edit must not audit');eq(o.showExternalAssetModal,true,'stale external-asset edit keeps modal open');
}
{
  const c=counters(),client={id:'c1',name:'Client',googleAccounts:[],instagramAccounts:[]};
  const o=wire({canManageAssets:()=>true,clients:[client],selectedAssetsClientId:'c1',externalAssetType:'GOOGLE',externalAssetForm:{id:null,accountName:' New ',loginAccount:' login ',note:' note '},defaultExternalAssetForm:()=>({}),accountUid:()=> 'g1',showExternalAssetModal:true},c);
  shipped.saveExternalAsset.call(o);eq(client.googleAccounts.length,1,'valid external asset create');eq(client.googleAccounts[0].id,'g1','valid external asset generated id');eq(c.persist,1,'valid external asset persists once');eq(c.audit,1,'valid external asset audits once');eq(o.showExternalAssetModal,false,'valid external asset closes modal');
}
{
  const c=counters(),client={id:'c1',name:'Client',googleAccounts:[],instagramAccounts:[]};
  const stale={id:'gone',accountName:'Gone'},o=wire({canManageAssets:()=>true,clients:[client],selectedAssetsClientId:'c1'},c);
  shipped.deleteExternalAsset.call(o,'GOOGLE',stale);eq(c.confirm,0,'stale external-asset delete must not open confirmation');eq(c.persist,0,'stale external-asset delete must not persist');
}
{
  const c=counters(),row={id:'g1',accountName:'Live'},client={id:'c1',name:'Client',googleAccounts:[row],instagramAccounts:[]};
  const o=wire({canManageAssets:()=>true,clients:[client],selectedAssetsClientId:'c1'},c);
  shipped.deleteExternalAsset.call(o,'GOOGLE',row);eq(c.confirm,1,'live external asset opens confirmation');client.googleAccounts=[];c.confirmCb();eq(c.persist,0,'external asset disappearing before confirmation must not persist');eq(c.audit,0,'external asset disappearing before confirmation must not audit');
}

// Media tools: stale edit/delete are fail-closed; valid create/delete retain the
// historical single-write behavior. normalizeMediaTool is a dependency, not a
// copied implementation, so this test stays focused on authoritative row identity.
{
  const c=counters(),o=wire({toolForm:{id:'gone',name:'Tool',bindings:['c1'],seats:1,loginPassword:''},normalizeMediaTool:x=>x,mediaTools:[],showToolModal:true,accountUid:()=> 'tool-new',toolPasswordVisible:{}},c);
  shipped.saveMediaTool.call(o);eq(o.mediaTools.length,0,'stale media-tool edit must not create');eq(c.persist,0,'stale media-tool edit must not persist');eq(c.audit,0,'stale media-tool edit must not audit');eq(o.showToolModal,true,'stale media-tool edit keeps modal open');
}
{
  const c=counters(),o=wire({toolForm:{id:null,name:'Tool',bindings:['c1'],seats:2,loginPassword:''},normalizeMediaTool:x=>x,mediaTools:[],showToolModal:true,accountUid:()=> 't1',toolPasswordVisible:{}},c);
  shipped.saveMediaTool.call(o);eq(o.mediaTools.length,1,'valid media tool create');eq(o.mediaTools[0].id,'t1','valid media tool id');eq(c.persist,1,'valid media tool persists once');eq(c.audit,1,'valid media tool audits once');
}
{
  const c=counters(),o=wire({mediaTools:[],toolPasswordVisible:{}},c),stale={id:'gone',name:'Gone',bindings:[]};
  shipped.deleteMediaTool.call(o,stale);eq(c.confirm,0,'stale media-tool delete must not confirm');eq(c.persist,0,'stale media-tool delete must not persist');
}
{
  const c=counters(),tool={id:'t1',name:'Live',bindings:['c1']},o=wire({mediaTools:[tool],toolPasswordVisible:{t1:true}},c);
  shipped.deleteMediaTool.call(o,tool);eq(c.confirm,1,'live media tool opens confirmation');o.mediaTools=[];c.confirmCb();eq(c.persist,0,'media tool disappearing before confirmation must not persist');eq(c.audit,0,'media tool disappearing before confirmation must not audit');
}

// Reminder types already guard stale edits, duplicates, permissions and system
// deletion. Lock those semantics and add authoritative membership/usage rechecks
// around the asynchronous confirmation boundary.
{
  const c=counters(),type={key:'CUSTOM_1',name:'Old',system:false},o=wire({canManageReminderTypes:()=>true,reminderTypes:[type],reminderTypeForm:{key:'CUSTOM_1',name:' New '},newAlertForm:{typeKey:'IP'},resetReminderTypeForm:()=>{o.reset=true}},c);
  shipped.saveReminderType.call(o);eq(type.name,'New','valid reminder type edit trims and saves');eq(c.persist,1,'valid reminder type edit persists once');eq(c.audit,1,'valid reminder type edit audits once');ok(o.reset,'valid reminder type edit resets form');
}
{
  const c=counters(),o=wire({canManageReminderTypes:()=>true,reminderTypes:[],reminderTypeForm:{key:'gone',name:'Name'},newAlertForm:{typeKey:'IP'},resetReminderTypeForm:()=>{}},c);
  shipped.saveReminderType.call(o);eq(c.persist,0,'stale reminder type edit does not persist');eq(c.audit,0,'stale reminder type edit does not audit');
}
{
  const c=counters(),stale={key:'CUSTOM_GONE',name:'Gone',system:false},o=wire({canManageReminderTypes:()=>true,reminderTypes:[],reminderTypeUsageCount:()=>0,newAlertForm:{typeKey:'IP'},alertTypeFilter:'ALL'},c);
  shipped.deleteReminderType.call(o,stale);eq(c.confirm,0,'stale reminder type delete must not confirm');eq(c.persist,0,'stale reminder type delete must not persist');
}
{
  const c=counters(),type={key:'CUSTOM_1',name:'Live',system:false};let usage=0;
  const o=wire({canManageReminderTypes:()=>true,reminderTypes:[type],reminderTypeUsageCount:()=>usage,newAlertForm:{typeKey:'IP'},alertTypeFilter:'ALL'},c);
  shipped.deleteReminderType.call(o,type);eq(c.confirm,1,'unused live reminder type opens confirmation');usage=1;c.confirmCb();eq(o.reminderTypes.length,1,'reminder type becoming used before confirmation is preserved');eq(c.persist,0,'new usage before confirmation blocks persist');eq(c.audit,0,'new usage before confirmation blocks audit');
}

console.log('BUSINESS_RESOURCE_CATALOG_MUTATIONS_OK: external-asset=stale-edit-deny+create+delete-recheck; media-tool=stale-edit-deny+create+delete-recheck; reminder-type=edit-stale-safe+delete-membership-usage-recheck; valid=single-write; provenance=final-shipped-vm');
