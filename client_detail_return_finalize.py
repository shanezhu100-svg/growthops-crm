from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
adapter_path=root/'dist'/'cloud-adapter.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')
adapter=adapter_path.read_text(encoding='utf-8')

def replace_once(text,old,new,label):
    count=text.count(old)
    if count!=1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Scoped page navigation: resolve the final client before Vue exposes the page.
# “全部客户” remains an explicit in-page option; it is not a transition state.
# -----------------------------------------------------------------------------
nav_marker="    navigateTo(page){"
scoped_helper="""    prepareScopedPageClient(page){
      const scopedPages=new Set(['assets','ads','sop']);
      if(!scopedPages.has(page)||page===this.currentPage)return;
      const active=(this.activeClients||[]).filter(c=>c&&!c.archived);
      if(!active.length)return;
      const resolvedId=id=>{
        const text=String(id??'').trim();
        if(!text||text==='0'||text.toUpperCase()==='ALL')return null;
        return active.find(c=>String(c.id)===text)?.id??null;
      };
      let sourceId=null;
      if(this.currentPage==='assets')sourceId=resolvedId(this.selectedAssetsClientId);
      else if(this.currentPage==='ads')sourceId=resolvedId(this.selectedAdsClientId);
      else if(this.currentPage==='sop')sourceId=resolvedId(this.selectedSopClientId);
      const ownId=page==='assets'?resolvedId(this.selectedAssetsClientId):(page==='ads'?resolvedId(this.selectedAdsClientId):resolvedId(this.selectedSopClientId));
      const preferred=sourceId??ownId??resolvedId(this.selectedClientId)??active[0].id;
      if(page==='assets'){
        this.selectedAssetsClientId=preferred;
        return;
      }
      if(page==='ads'){
        this.selectedAdsClientId=preferred;
        this.syncAdsAccountSelection();
        return;
      }
      const changed=String(this.selectedSopClientId??'')!==String(preferred);
      this.selectedSopClientId=preferred;
      this.syncSopAccountSelection(changed);
    },
    navigateTo(page){"""
html=replace_once(html,nav_marker,scoped_helper,'navigateTo method')

permission_marker="if(!this.canViewPage(page)){this.notify('当前角色没有访问该页面的权限');return}if(page==='assets'"
permission_new="if(!this.canViewPage(page)){this.notify('当前角色没有访问该页面的权限');return}this.prepareScopedPageClient(page);if(page==='assets'"
html=replace_once(html,permission_marker,permission_new,'navigate permission marker')

# Some earlier finalizers may remove/reformat the canonical mounted hash router.
# If its direct writes still survive, prepend the same scope resolver. Never add a
# second hash router just to satisfy a build marker.
for old,new,label in (
    ('this.currentPage=hash','this.prepareScopedPageClient(hash);this.currentPage=hash','mounted initial hash writer'),
    ('this.currentPage=h','this.prepareScopedPageClient(h);this.currentPage=h','mounted hashchange writer'),
):
    count=html.count(old)
    if count>1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    if count==1:
        html=html.replace(old,new,1)

# -----------------------------------------------------------------------------
# Client-detail source-aware return.
# -----------------------------------------------------------------------------
old_method="    openClientDetail(id){this.selectedClientId=id;this.credentialsVisible=false;this.resetAssetPager('detail');this.navigateTo('client-detail')},"
new_method="""    openClientDetail(id,sourcePage=''){
      const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);
      const requestedSource=String(sourcePage||'').trim();
      const currentSource=String(this.currentPage||'').trim();
      const source=allowedSources.has(requestedSource)?requestedSource:(allowedSources.has(currentSource)?currentSource:'clients');
      this.clientDetailReturnPage=source;
      try{sessionStorage.setItem('growthops_client_detail_return_page',source)}catch(_e){}
      if(source==='assets')this.selectedAssetsClientId=id;
      this.selectedClientId=id;
      this.credentialsVisible=false;
      this.resetAssetPager('detail');
      this.navigateTo('client-detail');
    },
    returnFromClientDetail(){
      const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);
      let storedSource='';
      try{storedSource=String(sessionStorage.getItem('growthops_client_detail_return_page')||'').trim()}catch(_e){}
      const memorySource=String(this.clientDetailReturnPage||'').trim();
      const source=allowedSources.has(storedSource)?storedSource:(allowedSources.has(memorySource)?memorySource:'clients');
      if(source==='assets'&&this.selectedClientId!==null&&this.selectedClientId!==undefined)this.selectedAssetsClientId=this.selectedClientId;
      this.clientDetailReturnPage='';
      try{sessionStorage.removeItem('growthops_client_detail_return_page')}catch(_e){}
      this.navigateTo(source);
    },"""
html=replace_once(html,old_method,new_method,'openClientDetail method')

old_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
new_back='<button type="button" @click="returnFromClientDetail()" class="w-10 h-10 rounded-xl border border-slate-200 bg-white" title="返回上一来源页面"><i class="fa-solid fa-arrow-left"></i></button>'
html=replace_once(html,old_back,new_back,'client-detail fixed back button')

old_assets_detail='<button v-if="selectedAssetsClient && selectedAssetsClientId!==0" @click="openClientDetail(selectedAssetsClient.id)"'
new_assets_detail='<button v-if="selectedAssetsClient && selectedAssetsClientId!==0" @click="openClientDetail(selectedAssetsClient.id,\'assets\')"'
html=replace_once(html,old_assets_detail,new_assets_detail,'account-assets detail shortcut')

# -----------------------------------------------------------------------------
# Cloud/session routing must resolve client scope before currentPage.
# -----------------------------------------------------------------------------
old_adapter_route="if(allowed.includes(h)&&vm.canViewPage(h))vm.currentPage=h;"
new_adapter_route="if(allowed.includes(h)&&vm.canViewPage(h)){vm.prepareScopedPageClient?.(h);vm.currentPage=h;}"
adapter=replace_once(adapter,old_adapter_route,new_adapter_route,'cloud adapter route')

# -----------------------------------------------------------------------------
# Runtime bridge: it runs in capture phase, so it must obey the same navigation
# state rather than overriding Vue after the fact.
# -----------------------------------------------------------------------------
old_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','client-form','client-detail']);"
new_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','assets','client-form','client-detail']);"
bridge=replace_once(bridge,old_scroll_pages,new_scroll_pages,'UI bridge scroll page set')

bridge_nav="""  const navigateWithPageScroll=(page,sourceHint)=>{
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage,sourceHint);"""
bridge_nav_new="""  const navigateWithPageScroll=(page,sourceHint)=>{
    const sourcePage=vm.currentPage;
    if(page!==sourcePage)vm.prepareScopedPageClient?.(page);
    if(sourcePage)rememberPageScroll(sourcePage,sourceHint);"""
bridge=replace_once(bridge,bridge_nav,bridge_nav_new,'UI bridge navigation')

old_finalize="  const finalizeClientListNavigation=()=>navigateWithPageScroll('clients');"
new_finalize="""  const CLIENT_DETAIL_RETURN_KEY='growthops_client_detail_return_page';
  const CLIENT_DETAIL_RETURN_PAGES=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);
  const readClientDetailReturnPage=()=>{
    let stored='';
    try{stored=String(sessionStorage.getItem(CLIENT_DETAIL_RETURN_KEY)||'').trim()}catch{}
    const memory=String(vm.clientDetailReturnPage||'').trim();
    return CLIENT_DETAIL_RETURN_PAGES.has(stored)?stored:(CLIENT_DETAIL_RETURN_PAGES.has(memory)?memory:'clients');
  };
  const clearClientDetailReturnPage=()=>{
    vm.clientDetailReturnPage='';
    try{sessionStorage.removeItem(CLIENT_DETAIL_RETURN_KEY)}catch{}
  };
  const returnFromClientDetailBridge=button=>{
    const target=readClientDetailReturnPage();
    if(target==='assets'&&vm.selectedClientId!==null&&vm.selectedClientId!==undefined)vm.selectedAssetsClientId=vm.selectedClientId;
    clearClientDetailReturnPage();
    navigateWithPageScroll(target,button);
  };
  const finalizeClientSaveNavigation=()=>navigateWithPageScroll('client-detail');"""
bridge=replace_once(bridge,old_finalize,new_finalize,'UI bridge client-list finalizer')

old_runtime_back="if(button.querySelector('i.fa-arrow-left'))bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button));"
new_runtime_back="if(button.querySelector('i.fa-arrow-left'))bind(button,'client-detail-back',button=>returnFromClientDetailBridge(button));"
bridge=replace_once(bridge,old_runtime_back,new_runtime_back,'UI bridge hard-coded detail back')

bridge=replace_once(bridge,'            finalizeClientListNavigation();','            finalizeClientSaveNavigation();','UI bridge client save return')

index_path.write_text(html,encoding='utf-8')
bridge_path.write_text(bridge,encoding='utf-8')
adapter_path.write_text(adapter,encoding='utf-8')
index_sha=hashlib.sha256(index_path.read_bytes()).hexdigest()
bridge_sha=hashlib.sha256(bridge_path.read_bytes()).hexdigest()
adapter_sha=hashlib.sha256(adapter_path.read_bytes()).hexdigest()
print(f'CLIENT_DETAIL_RETURN_FINALIZE_OK: index={index_sha}; bridge={bridge_sha}; adapter={adapter_sha}')
print('SCOPED_PAGE_NAVIGATION_FINALIZE_OK: assets=preselected; ads=preselected; sop=preselected')
