import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const appDir=path.join(process.cwd(),'dist','app');
if(!fs.existsSync(appDir))throw new Error('BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: dist/app missing');
const files=fs.readdirSync(appDir).filter(name=>/^app-inline-\d+\.js$/.test(name)).sort();
const bundle=files.map(name=>fs.readFileSync(path.join(appDir,name),'utf8')).join('\n');
function scanBalanced(text,start,openChar,closeChar){let depth=0,quote='',escaped=false,lineComment=false,blockComment=false;for(let i=start;i<text.length;i+=1){const ch=text[i],next=text[i+1]||'';if(lineComment){if(ch==='\n')lineComment=false;continue}if(blockComment){if(ch==='*'&&next==='/'){blockComment=false;i+=1}continue}if(quote){if(escaped){escaped=false;continue}if(ch==='\\'){escaped=true;continue}if(ch===quote)quote='';continue}if(ch==='/'&&next==='/'){lineComment=true;i+=1;continue}if(ch==='/'&&next==='*'){blockComment=true;i+=1;continue}if(ch==='"'||ch==="'"||ch==='`'){quote=ch;continue}if(ch===openChar)depth+=1;else if(ch===closeChar&&--depth===0)return i}throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: unmatched ${openChar}`)}
function extractMethod(name){const m=new RegExp(`(?:^|[,\\n])\\s*${name}\\s*\\(`,'m').exec(bundle);if(!m)throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: ${name} missing`);const start=m.index+m[0].lastIndexOf(name),paren=bundle.indexOf('(',start+name.length),parenEnd=scanBalanced(bundle,paren,'(',')');let open=parenEnd+1;while(/\s/.test(bundle[open]||''))open+=1;const end=scanBalanced(bundle,open,'{','}');return bundle.slice(start,end+1).trim()}
const names=['addAdCampaign','editAdCampaign','removeAdCampaign','addAdSet','removeAdSet','addCreative','removeCreative'];
let methods;try{methods=vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`,{Array,Object,String,Number,Math,JSON,Date,Set,Promise},{timeout:1000})}catch(error){throw new Error(`BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: compile: ${error.message}`)}
const fail=m=>{throw new Error('BUSINESS_AD_STRUCTURE_MUTATIONS_FAILED: '+m)},eq=(a,b,m)=>{if(a!==b)fail(`${m}; expected=${b}; actual=${a}`)},ok=(v,m)=>{if(!v)fail(m)};
const makeTree=()=>({id:'client-1',name:'Client',adCampaigns:[{id:'campaign-1',name:'Campaign',isSaved:true,adSets:[{id:'set-1',name:'Set',ads:[{id:'ad-1',name:'Ad'}]}]}]});
function subject(){const client=makeTree(),state={persist:0,barrier:0,audit:0,notices:[],confirm:null,campaignSeq:0,setSeq:0,adSeq:0};const s=Object.assign({},methods,{clients:[client],selectedAdsClient:client,selectedAdsAccount:{id:'account-1'},auditLogs:[],emptyAdCampaign(){state.campaignSeq+=1;return{id:`campaign-new-${state.campaignSeq}`,name:'',isSaved:false,adSets:[]}},emptyAdSet(){state.setSeq+=1;return{id:`set-new-${state.setSeq}`,name:'',ads:[]}},emptyCreative(){state.adSeq+=1;return{id:`ad-new-${state.adSeq}`,name:''}},persist(){state.persist+=1},persistAdStructureBarrier(){state.barrier+=1;return Promise.resolve(true)},logAudit(){state.audit+=1},notify(m){state.notices.push(String(m))},askConfirm(_o,cb){state.confirm=cb}});return{s,client,state}}

// Stale targets remain fail-closed before the durable barrier.
{const {s,state}=subject(),stale={id:'missing-campaign',isSaved:true,adSets:[]};s.editAdCampaign(stale);eq(stale.isSaved,true,'stale campaign edit detached unchanged');eq(state.persist,0,'stale campaign edit no persist');eq(state.barrier,0,'stale campaign edit no barrier');ok(state.notices.some(m=>m.includes('不存在')||m.includes('刷新')),'stale campaign edit notice')}
{const {s,state}=subject(),stale={id:'missing-campaign',name:'Missing',adSets:[]};s.removeAdCampaign(stale);if(state.confirm)state.confirm();eq(state.persist,0,'stale campaign delete no persist');eq(state.barrier,0,'stale campaign delete no barrier');eq(state.audit,0,'stale campaign delete no audit')}
{const {s,state}=subject(),stale={id:'missing-campaign',adSets:[]};s.addAdSet(stale);eq(stale.adSets.length,0,'stale add-set detached unchanged');eq(state.barrier,0,'stale add-set no barrier')}
{const {s,state}=subject(),stale={id:'missing-set',ads:[]};s.addCreative(stale);eq(stale.ads.length,0,'stale add-creative detached unchanged');eq(state.barrier,0,'stale add-creative no barrier')}

// Valid adds/edits use one durable ACK and suppress legacy debounced persistence.
{const {s,client,state}=subject();await s.addAdCampaign();eq(client.adCampaigns.length,2,'campaign add once');eq(state.persist,0,'campaign add legacy persist suppressed');eq(state.barrier,1,'campaign add barrier once')}
{const {s,client,state}=subject();await s.editAdCampaign(client.adCampaigns[0]);eq(client.adCampaigns[0].isSaved,false,'campaign edit marks unsaved');eq(state.persist,0,'campaign edit legacy persist suppressed');eq(state.barrier,1,'campaign edit barrier once')}
{const {s,client,state}=subject(),campaign=client.adCampaigns[0];await s.addAdSet(campaign);eq(campaign.adSets.length,2,'add-set once');eq(state.persist,0,'add-set legacy persist suppressed');eq(state.barrier,1,'add-set barrier once')}
{const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0];await s.addCreative(set);eq(set.ads.length,2,'add-creative once');eq(state.persist,0,'add-creative legacy persist suppressed');eq(state.barrier,1,'add-creative barrier once')}

// Confirmation-time disappearance still blocks deletion before ACK/audit.
{const {s,client,state}=subject(),target=client.adCampaigns[0];s.removeAdCampaign(target);ok(typeof state.confirm==='function','campaign delete confirms');client.adCampaigns=[];state.confirm();eq(state.barrier,0,'campaign disappearance no barrier');eq(state.audit,0,'campaign disappearance no audit')}
{const {s,client,state}=subject(),campaign=client.adCampaigns[0],set=campaign.adSets[0];s.removeAdSet(campaign,set);campaign.adSets=[];state.confirm();eq(state.barrier,0,'set disappearance no barrier');eq(state.audit,0,'set disappearance no audit')}
{const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0],ad=set.ads[0];s.removeCreative(set,ad);set.ads=[];state.confirm();eq(state.barrier,0,'creative disappearance no barrier');eq(state.audit,0,'creative disappearance no audit')}

// Valid deletes are one durable write and one historical audit.
{const {s,client,state}=subject(),target=client.adCampaigns[0];s.removeAdCampaign(target);await state.confirm();eq(client.adCampaigns.length,0,'campaign delete removes');eq(state.persist,0,'campaign delete legacy persist suppressed');eq(state.barrier,1,'campaign delete barrier once');eq(state.audit,1,'campaign delete audits once')}
{const {s,client,state}=subject(),campaign=client.adCampaigns[0],set=campaign.adSets[0];s.removeAdSet(campaign,set);await state.confirm();eq(campaign.adSets.length,0,'set delete removes');eq(state.persist,0,'set delete legacy persist suppressed');eq(state.barrier,1,'set delete barrier once');eq(state.audit,1,'set delete audits once')}
{const {s,client,state}=subject(),set=client.adCampaigns[0].adSets[0],ad=set.ads[0];s.removeCreative(set,ad);await state.confirm();eq(set.ads.length,0,'creative delete removes');eq(state.persist,0,'creative delete legacy persist suppressed');eq(state.barrier,1,'creative delete barrier once');eq(state.audit,1,'creative delete audits once')}

// A selected-client replacement while confirmation is open invalidates the old closure.
{const {s,client,state}=subject(),target=client.adCampaigns[0];s.removeAdCampaign(target);const replacement=makeTree();s.clients=[replacement];s.selectedAdsClient=replacement;state.confirm();eq(state.barrier,0,'client replacement blocks campaign delete barrier');eq(state.audit,0,'client replacement blocks campaign delete audit');eq(client.adCampaigns.length,1,'old client untouched after authority changes')}

console.log('BUSINESS_AD_STRUCTURE_MUTATIONS_OK: campaign=add+edit-current+delete-recheck; adset=live-parent+add+delete-recheck; creative=unique-live-parent+add+delete-recheck; confirm-client-authority=rechecked; stale=zero-persist-audit-barrier; valid=single-durable-ACK+legacy-persist-suppressed; provenance=final-shipped-vm');
await import('./test_business_ad_structure_persistence_ack.mjs');
