from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'
BRIDGE = ROOT / 'dist' / 'cloud-ui-action-bridge.js'

security = SECURITY.read_text(encoding='utf-8')
bridge = BRIDGE.read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('CLIENT_ACCOUNT_CORRESPONDENCE_FINALIZE_FAILED: ' + message)


def replace_security_block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global security
    start = security.find(start_marker)
    end = security.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        fail('unable to locate ' + label)
    security = security[:start] + replacement + security[end:]


old_summary = r'''  const summaryForCredentialRow=row=>{
    if(!accountSafeSummaryData)return null;
    if(row.platform==='facebook'||row.platform==='tiktok')return accountSafeSummaryData?.[row.platform]||null;
    const list=row.platform==='google'?accountSafeSummaryData?.googleAccounts:accountSafeSummaryData?.instagramAccounts;
    if(!Array.isArray(list)||!list.length)return null;
    const current=currentExternalAssetAccount(row.platform);
    const currentId=String(current?.id??'');
    if(currentId){
      const match=list.find(item=>String(item?.id??'')===currentId);
      if(match)return match;
    }
    return list.length===1?list[0]:null;
  };
'''
new_summary = r'''  const credentialClientForContext=()=>{
    const directId=String(vm.selectedClientId??'');
    if(vm.currentPage==='client-detail'||vm.currentPage==='client-form'){
      if(vm.selectedClient&&String(vm.selectedClient?.id??'')===directId)return vm.selectedClient;
      const match=(Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===directId);
      return match||vm.selectedClient||vm.currentClient||null;
    }
    if(isAccountAssetPage()){
      const assetId=String(vm.selectedAssetsClientId??'');
      if(assetId==='0'||assetId.toUpperCase()==='ALL')return null;
      if(vm.selectedAssetsClient&&String(vm.selectedAssetsClient?.id??'')===assetId)return vm.selectedAssetsClient;
      return (Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===assetId)||vm.selectedAssetsClient||null;
    }
    return vm.selectedClient||vm.selectedAssetsClient||vm.currentClient||null;
  };
  const credentialPlatformConfig=platform=>({
    facebook:{listKey:'fbAccounts',summaryKey:'facebookAccounts',pager:'FB',legacyKey:'facebook'},
    tiktok:{listKey:'tkAccounts',summaryKey:'tiktokAccounts',pager:'TK',legacyKey:'tiktok'},
    google:{listKey:'googleAccounts',summaryKey:'googleAccounts',pager:'GOOGLE',legacyKey:''},
    instagram:{listKey:'instagramAccounts',summaryKey:'instagramAccounts',pager:'INSTAGRAM',legacyKey:''},
  }[platform]||null);
  const currentCredentialAccount=(row,config)=>{
    const client=credentialClientForContext();
    const list=Array.isArray(client?.[config.listKey])?client[config.listKey]:[];
    if(!list.length)return null;
    const scope=vm.currentPage==='client-detail'?'detail':vm.currentPage==='client-form'?'form':'assets';
    if(vm.currentPage!=='client-form'&&typeof vm.getPagedItem==='function'){
      const paged=vm.getPagedItem(list,scope,config.pager);
      if(paged)return paged;
    }
    const tokens=cardIdentityTokens(row?.card);
    const tokenMatches=list.filter(item=>{
      const id=String(item?.id??'').trim().toLowerCase();
      if(id&&tokens.includes(id))return true;
      const identifiers=[item?.accountId,item?.adAccountId,item?.bmId,item?.name].map(value=>String(value??'').trim().toLowerCase()).filter(Boolean);
      return identifiers.some(value=>tokens.includes(value));
    });
    if(tokenMatches.length===1)return tokenMatches[0];
    if(vm.currentPage==='client-form'&&list.length>1){
      const platformRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform);
      const rowIndex=platformRows.findIndex(candidate=>candidate.card===row.card);
      if(rowIndex>=0&&rowIndex<list.length)return list[rowIndex];
    }
    return list.length===1?list[0]:null;
  };
  const summaryForCredentialRow=row=>{
    if(!accountSafeSummaryData)return null;
    const config=credentialPlatformConfig(row.platform);
    if(!config)return null;
    const summaries=Array.isArray(accountSafeSummaryData?.[config.summaryKey])?accountSafeSummaryData[config.summaryKey]:[];
    const current=currentCredentialAccount(row,config);
    const currentId=String(current?.id??'');
    if(currentId&&summaries.length){
      const match=summaries.find(item=>String(item?.id??'')===currentId);
      if(match)return match;
    }
    if(summaries.length===1)return summaries[0];
    if(config.legacyKey){
      const client=credentialClientForContext();
      const platformAccounts=Array.isArray(client?.[config.listKey])?client[config.listKey]:[];
      if(platformAccounts.length<=1)return accountSafeSummaryData?.[config.legacyKey]||null;
    }
    return null;
  };
'''
if security.count(old_summary) != 1:
    fail(f'unexpected legacy safe-summary resolver count: {security.count(old_summary)}')
security = security.replace(old_summary, new_summary, 1)

platform_block = r'''  const platformForCard=card=>{
    let node=card||null;
    for(let i=0;node&&i<9;i+=1,node=node.parentElement){
      const value=String(node.textContent||'').toLowerCase();
      if(value.includes('facebook'))return 'facebook';
      if(value.includes('tiktok'))return 'tiktok';
      if(value.includes('google'))return 'google';
      if(value.includes('instagram'))return 'instagram';
    }
    return '';
  };
'''
replace_security_block('  const platformForCard=card=>{','  const cardIdentityTokens=card=>{',platform_block,'four-platform card resolver')

# The final client-form presentation layer may have rewritten these helpers already,
# so patch by function boundaries rather than depending on an intermediate body.
card_block = r'''  const credentialAccountLabelTexts=['登录账号','登录邮箱','登录邮箱 / 手机号'];
  const credentialLabelCount=(root,label)=>[...root.querySelectorAll('*')].filter(el=>el.children.length===0&&cleanText(el)===label).length;
  const credentialAccountLabelCount=root=>credentialAccountLabelTexts.reduce((count,label)=>count+credentialLabelCount(root,label),0);
  const credentialCardForLabel=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i+=1,node=node.parentElement){
      if(credentialAccountLabelCount(node)===1&&credentialLabelCount(node,'密码 / 2FA')===1)return node;
    }
    return null;
  };
'''
replace_security_block('  const credentialLabelCount=','  const valueCellForLabel=label=>{',card_block,'credential card label resolver')

value_block = r'''  const valueCellForLabel=label=>{
    const labelText=cleanText(label);
    const kind=credentialAccountLabelTexts.includes(labelText)?'account':labelText==='密码 / 2FA'?'secret':'';
    if(kind){
      const host=credentialFormStatusHost(label,kind);
      if(host)return host;
    }
    const row=label?.parentElement;
    if(!row)return null;
    const children=[...row.children].filter(el=>el!==label);
    return children.length?children[children.length-1]:null;
  };
'''
replace_security_block('  const valueCellForLabel=label=>{','  const locateCredentialRows=()=>{',value_block,'credential value/status resolver')

locate_block = r'''  const locateCredentialRows=()=>{
    const rows=[];
    const accountLabels=new Set(credentialAccountLabelTexts);
    const labels=[...document.querySelectorAll('*')].filter(el=>el.children.length===0&&(accountLabels.has(cleanText(el))||cleanText(el)==='密码 / 2FA'));
    const seen=new Set();
    for(const label of labels){
      const card=credentialCardForLabel(label);
      if(!card||seen.has(card))continue;
      const platform=platformForCard(card);
      if(!platform)continue;
      seen.add(card);
      const accountLabel=credentialAccountLabelTexts.map(text=>exactLeaf(card,text)).find(Boolean)||null;
      const passwordLabel=exactLeaf(card,'密码 / 2FA');
      rows.push({card,platform,accountCell:valueCellForLabel(accountLabel),passwordCell:valueCellForLabel(passwordLabel)});
    }
    return rows.filter(row=>row.platform&&(row.accountCell||row.passwordCell));
  };
'''
replace_security_block('  const locateCredentialRows=()=>{','  const prepareInlineCell=(cell,kind)=>{',locate_block,'credential row resolver')

route_insert = r'''  const UI_ROUTE_STATE_KEY='growthops_ui_route_state_v1';
  const UI_ROUTE_PAGES=new Set(['dashboard','leads','clients','client-form','client-detail','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);
  const UI_ROUTE_SELECTION_KEYS=['selectedClientId','selectedAssetsClientId','selectedAdsClientId','selectedAnalyticsClientId','selectedSopClientId','selectedSopAccountKey'];
  let uiRouteStateRestored=false;
  let uiRouteHadAuthenticatedUser=false;
  let lastSavedUiRouteState='';
  const safeRouteScalar=value=>{
    if(value===null)return null;
    if(typeof value==='number'&&Number.isFinite(value))return value;
    if(typeof value==='string'&&value.length<=160)return value;
    return undefined;
  };
  const readUiRouteState=()=>{
    try{
      const raw=sessionStorage.getItem(UI_ROUTE_STATE_KEY);
      if(!raw)return null;
      const parsed=JSON.parse(raw);
      if(!parsed||typeof parsed!=='object'||!UI_ROUTE_PAGES.has(String(parsed.page||'')))return null;
      return parsed;
    }catch{return null}
  };
  const clearUiRouteState=()=>{
    try{sessionStorage.removeItem(UI_ROUTE_STATE_KEY)}catch{}
    lastSavedUiRouteState='';
  };
  const persistUiRouteState=()=>{
    if(!vm.currentUser||!uiRouteStateRestored)return;
    const page=String(vm.currentPage||'');
    if(!UI_ROUTE_PAGES.has(page))return;
    const state={page};
    for(const key of UI_ROUTE_SELECTION_KEYS){
      const value=safeRouteScalar(vm[key]);
      if(value!==undefined)state[key]=value;
    }
    const raw=JSON.stringify(state);
    if(raw===lastSavedUiRouteState)return;
    try{sessionStorage.setItem(UI_ROUTE_STATE_KEY,raw);lastSavedUiRouteState=raw}catch{}
    setPageUrl(page);
  };
  const restoreUiRouteState=()=>{
    if(uiRouteStateRestored||!vm.currentUser)return;
    uiRouteHadAuthenticatedUser=true;
    const stored=readUiRouteState();
    let hashPage='';
    try{hashPage=String(window.location.hash||'').replace(/^#/,'')}catch{}
    const page=UI_ROUTE_PAGES.has(hashPage)?hashPage:(stored?.page||'');
    if(stored){
      for(const key of UI_ROUTE_SELECTION_KEYS){
        if(!Object.prototype.hasOwnProperty.call(stored,key))continue;
        const value=safeRouteScalar(stored[key]);
        if(value!==undefined)vm[key]=value;
      }
    }
    if(page&&UI_ROUTE_PAGES.has(page))vm.currentPage=page;
    uiRouteStateRestored=true;
    if(page)setPageUrl(page);
    try{vm.$forceUpdate?.()}catch{}
    if(page&&typeof vm.$nextTick==='function')vm.$nextTick(()=>restorePageScrollInstant(page));
    persistUiRouteState();
  };
  const syncUiRouteState=()=>{
    if(vm.currentUser){uiRouteHadAuthenticatedUser=true;restoreUiRouteState();persistUiRouteState();return;}
    if(uiRouteHadAuthenticatedUser){clearUiRouteState();uiRouteStateRestored=false;uiRouteHadAuthenticatedUser=false;}
  };
'''
route_anchor = "  const CLIENT_DETAIL_RETURN_KEY='growthops_client_detail_return_page';\n"
if bridge.count(route_anchor) != 1:
    fail(f'unexpected route-state insertion anchor count: {bridge.count(route_anchor)}')
bridge = bridge.replace(route_anchor, route_insert + route_anchor, 1)

install_anchor = "    clearSessionRestoreCover();\n    observePageScroll();\n"
if bridge.count(install_anchor) != 1:
    fail(f'unexpected bridge install anchor count: {bridge.count(install_anchor)}')
bridge = bridge.replace(install_anchor, "    clearSessionRestoreCover();\n    syncUiRouteState();\n    observePageScroll();\n", 1)

watch_anchor = "  const observer=new MutationObserver(install);\n"
watch_block = r'''  let lastDetailClientId=String(vm.selectedClientId??'');
  const syncDetailClientPager=()=>{
    const next=String(vm.selectedClientId??'');
    if(next===lastDetailClientId)return;
    lastDetailClientId=next;
    if(vm.currentPage==='client-detail'&&typeof vm.resetAssetPager==='function')vm.resetAssetPager('detail');
  };
'''
if bridge.count(watch_anchor) != 1:
    fail(f'unexpected bridge observer anchor count: {bridge.count(watch_anchor)}')
bridge = bridge.replace(watch_anchor, watch_block + watch_anchor, 1)

interval_old = "  setInterval(install,250);\n"
interval_new = "  setInterval(()=>{syncDetailClientPager();install()},250);\n"
if bridge.count(interval_old) != 1:
    fail(f'unexpected bridge install interval count: {bridge.count(interval_old)}')
bridge = bridge.replace(interval_old, interval_new, 1)

route_region_start = bridge.find('const UI_ROUTE_STATE_KEY')
route_region_end = bridge.find('const CLIENT_DETAIL_RETURN_KEY', route_region_start)
if route_region_start < 0 or route_region_end <= route_region_start:
    fail('unable to bound route-state persistence region')
route_region = bridge[route_region_start:route_region_end]
for forbidden in ('TOKEN_KEY','loginAccount','loginPassword','password','twofa','credential','accountSafeSummary','Vault'):
    if forbidden.lower() in route_region.lower():
        fail('sensitive route-state marker found: ' + forbidden)

SECURITY.write_text(security, encoding='utf-8')
BRIDGE.write_text(bridge, encoding='utf-8')
print(
    'CLIENT_ACCOUNT_CORRESPONDENCE_FINALIZE_OK: '
    'safe-summary=account-id-correspondence+client-form-order-fallback+multi-account-fail-closed; '
    'platform-card=facebook+tiktok+google+instagram; login-label=alias-resolved-per-card; '
    'refresh=session-route-restore+selection-metadata-only; detail-client=pager-reset; '
    'security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest() + '; '
    'bridge=' + hashlib.sha256(BRIDGE.read_bytes()).hexdigest()
)
