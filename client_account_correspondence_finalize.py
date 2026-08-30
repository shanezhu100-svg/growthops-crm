from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'
BRIDGE = ROOT / 'dist' / 'cloud-ui-action-bridge.js'

security = SECURITY.read_text(encoding='utf-8')
bridge = BRIDGE.read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('CLIENT_ACCOUNT_CORRESPONDENCE_FINALIZE_FAILED: ' + message)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        fail('unable to locate ' + label)
    return text[:start] + replacement + text[end:]


# Safe-summary rows must follow the account that is actually visible/edited. The
# older FB/TK path used one platform-level summary, which is ambiguous as soon as a
# client has multiple accounts. Prefer per-account arrays + exact ID matching and
# fail closed when a multi-account row cannot be identified. Anchor on the stable
# summary function and the consolidated v5 renderer alias.
summary_block = r'''  const credentialClientForContext=()=>{
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
    // Legacy single-account workspaces may only have the old top-level FB/TK fields.
    // Never use that fallback when the visible client has multiple platform accounts.
    if(config.legacyKey){
      const client=credentialClientForContext();
      const platformAccounts=Array.isArray(client?.[config.listKey])?client[config.listKey]:[];
      if(platformAccounts.length<=1)return accountSafeSummaryData?.[config.legacyKey]||null;
    }
    return null;
  };
'''
security = replace_block(
    security,
    '  const summaryForCredentialRow=row=>{',
    '  const applyAccountSafeSummaryToCards=credentialUiV5Render;',
    summary_block,
    'safe-summary account correspondence block',
)

# Route persistence is deliberately metadata-only. Never persist login identifiers,
# passwords, session tokens, Vault data, forms, or whole client objects. Restore is
# gated on an authenticated vm.currentUser so refresh cannot expose an authenticated
# route before session restoration finishes. It is inserted immediately before the
# existing client-detail return authority so the two session route mechanisms remain
# separate and deterministic.
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
    if(vm.currentUser){
      uiRouteHadAuthenticatedUser=true;
      restoreUiRouteState();
      persistUiRouteState();
      return;
    }
    if(uiRouteHadAuthenticatedUser){
      clearUiRouteState();
      uiRouteStateRestored=false;
      uiRouteHadAuthenticatedUser=false;
    }
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

# Keep the selected client's detail pager isolated. openClientDetail() already resets
# it; this watcher is defense-in-depth for any future direct selectedClientId mutation.
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

# Explicitly fail closed if route persistence ever starts collecting sensitive state.
route_region_start = bridge.find("const UI_ROUTE_STATE_KEY")
route_region_end = bridge.find("const CLIENT_DETAIL_RETURN_KEY", route_region_start)
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
    'safe-summary=account-id-correspondence+multi-account-fail-closed; '
    'refresh=session-route-restore+selection-metadata-only; detail-client=pager-reset; '
    'security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest() + '; '
    'bridge=' + hashlib.sha256(BRIDGE.read_bytes()).hexdigest()
)
