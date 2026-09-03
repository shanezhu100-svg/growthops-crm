import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
function scanBalanced(text,start,openChar,closeChar){
  let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;
  for(let i=start;i<text.length;i+=1){const ch=text[i],next=text[i+1]||'';
    if(lineComment){if(ch==='\n')lineComment=false;continue}if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}
    if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}
    if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}
    if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}if(ch===openChar)depth+=1;else if(ch===closeChar&&--depth===0)return i;}
  throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: unmatched ${openChar}`);
}
function extractMethod(name){
  const m=new RegExp(`(?:^|[,\\n])\\s*${name}\\s*\\(`,'m').exec(bundle);if(!m)throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: ${name} missing`);
  const start=m.index+m[0].lastIndexOf(name),paren=bundle.indexOf('(',start+name.length),parenEnd=scanBalanced(bundle,paren,'(',')');let open=parenEnd+1;while(/\s/.test(bundle[open]||''))open+=1;
  const end=scanBalanced(bundle,open,'{','}');return bundle.slice(start,end+1).trim();
}
const names=['addAdCampaign','editAdCampaign','removeAdCampaign','addAdSet','removeAdSet','addCreative','removeCreative'];
let methods;try{methods=vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`,{Array,Object,String,Number,Math,JSON,Date,Set},{timeout:1000})}catch(error){throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: compile: ${error.message}`)}
const fail=m=>{throw new Error('BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: '+m)},eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${b}; actual=${a}`)},ok=(v,m)=>{if(!v)fail(m)};
const makeTree=()=>({id:'client-1',name:'Client',adCampaigns:[{id:'campaign-1',name:'Campaign',isSaved:true,adSets:[{id:'set-1',name:'Set',ads:[{id:'ad-1',name:'Ad'}]}]}]});
function subject(){
  const client=makeTree(),state={persist:0,audit:0,notices:[],confirm:null,campaignSeq:0,setSeq:0,adSeq:0};
  const s=Object.assign({},methods,{selectedAdsClient:client,selectedAdsAccount:{id:'account-1'},
    emptyAdCampaign(){state.campaignSeq+=1;return{id:`campaign-new-${state.campaignSeq}`,name:'',isSaved:false,adSets:[]}},
    emptyAdSet(){state.setSeq+=1;return{id:`set-new-${state.setSeq}`,name:'',ads:[]}},
    emptyCreative(){state.adSeq+=1;return{id:`ad-new-${state.adSeq}`,name:''}},
    persist(){state.persist+=1},logAudit(){state.audit+=1},notify(m){state.notices.push(String(m))},askConfirm(_o,cb){state.confirm=cb}});
  return{s,client,state};
}

// A stale campaign object must not be edited or persisted.
{
  const {s,state}=subject(),stale={id:'missing-campaign',isSaved:true,adSets:[]};s.editAdCampaign(stale);
  eq(stale.isSaved,true,'stale campaign edit leaves detached object unchanged');eq(state.persist,0,'stale campaign edit must not persist');ok(state.notices.some(m=>m.includes('不存在')||m.includes('刷新')),'stale campaign edit explains stale target');
}
// Valid top-level add and current campaign edit remain single writes.
{
  const {s,client,state}=subject();s.addAdCampaign();eq(client.adCampaigns.length,2,'valid campaign add inserts once');eq(state.persist,1,'valid campaign add persists once');
}
{
  const {s,client,state}=subject();s.editAdCampaign(client.adCampaigns[0]);eq(client.adCampaigns[0].isSaved,false,'valid campaign edit marks unsaved');eq(state.persist,1,'valid campaign edit persists once');
}
// Campaign deletion must fail closed if stale before confirmation or removed while confirmation is open.
{
  const {s,state}=subject(),stale={id:'missing-campaign',name:'Missing',adSets:[]};s.removeAdCampaign(stale);if(state.confirm)state.confirm();eq(state.persist,0,'stale campaign delete must not persist');eq(state.audit,0,'stale campaign delete must not audit');
}
{
  const {s,client,state}=subject(),target=client.adCampaigns[0];s.removeAdCampaign(target);ok(typeof state.confirm==='function','current campaign delete asks confirmation');client.adCampaigns=[];state.confirm();eq(state.persist,0,'campaign removed during confirm must not persist');eq(state.audit,0,'campaign removed during confirm must not audit');
}
{
  const {s,client,state}=subject(),target=client.adCampaigns[0];s.removeAdCampaign(target);state.confirm();eq(client.adCampaigns.length,0,'valid campaign delete removes target');eq(state.persist,1,'valid campaign delete persists once');eq(state.audit,1,'valid campaign delete audits once');
}
// Ad-set mutation must resolve a live campaign and a live set by id.
{
  const {s,state}=subject(),stale={id:'missing-campaign',adSets:[]};s.addAdSet(stale);eq(stale.adSets.length,0,'stale campaign add-set leaves detached tree unchanged');eq(state.persist,0,'stale campaign add-set must not persist');
}
{
  const {s,client,state}=subject(),campaign=client.adCampaigns[0];s.addAdSet(campaign);eq(campaign.adSets.length,2,'valid add-set inserts once');eq(state.persist,1,'valid add-set persists once');
}
{
  const {s,client,state}=subject(),campaign=client.adCampaigns[0],stale={id:'missing-set',name:'Missing',ads:[]};s.removeAdSet(campaign,stale);if(state.confirm)state.confirm();eq(state.persist,0,'stale set delete must not persist');eq(state.audit,0,'stale set delete must not audit');
}
{
  const {s,client,state}=subject(),campaign=client.adCampaigns[0],set=campaign.adSets[0];s.removeAdSet(campaign,set);campaign.adSets=[];state.confirm();eq(state.persist,0,'set removed during confirm must not persist');eq(state.audit,0,'set removed during confirm must not audit');
}
{
  const {s,client,state}=subject(),campaign=client.adCampaigns[0],set=campaign.adSets[0];s.removeAdSet(campaign,set);state.confirm();eq(campaign.adSets.length,0,'valid set delete removes target');eq(state.persist,1,'valid set delete persists once');eq(state.audit,1,'valid set delete audits once');
}
// Creative mutations must operate only on a live ad-set under the selected client.
{
  const {s,state}=subject(),stale={id:'missing-set',ads:[]};s.addCreative(stale);eq(stale.ads.length,0,'stale set add-creative leaves detached object unchanged');eq(state.persist,0,'stale set add-creative must not persist');
}
{
  const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0];s.addCreative(set);eq(set.ads.length,2,'valid add-creative inserts once');eq(state.persist,1,'valid add-creative persists once');
}
{
  const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0],stale={id:'missing-ad',name:'Missing'};s.removeCreative(set,stale);if(state.confirm)state.confirm();eq(state.persist,0,'stale creative delete must not persist');eq(state.audit,0,'stale creative delete must not audit');
}
{
  const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0],ad=set.ads[0];s.removeCreative(set,ad);set.ads=[];state.confirm();eq(state.persist,0,'creative removed during confirm must not persist');eq(state.audit,0,'creative removed during confirm must not audit');
}
{
  const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0],ad=set.ads[0];s.removeCreative(set,ad);state.confirm();eq(set.ads.length,0,'valid creative delete removes target');eq(state.persist,1,'valid creative delete persists once');eq(state.audit,1,'valid creative delete audits once');
}
console.log('BUSINESS_AD_STRUCTURE_MUTATIONS_OK: campaign=add+edit-current+stale-edit-deny+delete-recheck; adset=live-parent+add+delete-recheck; creative=live-parent+add+delete-recheck; stale=zero-persist-audit; valid=single-write; provenance=final-shipped-vm');
