from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
adapter_path=root/'dist'/'cloud-adapter.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')
adapter=adapter_path.read_text(encoding='utf-8')

# Keep all client-scoped pages on one pre-render selection path.  Aggregate
# modes remain user-selectable inside the page, but are never used as a
# transient navigation state while entering assets / ads / SOP.
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
if html.count(nav_marker)!=1:
    raise SystemExit(f'Unexpected navigateTo method count: {html.count(nav_marker)}')
html=html.replace(nav_marker,scoped_helper,1)

permission_marker="if(!this.canViewPage(page)){this.notify('当前角色没有访问该页面的权限');return}if(page==='assets'"
permission_replacement="if(!this.canViewPage(page)){this.notify('当前角色没有访问该页面的权限');return}this.prepareScopedPageClient(page);if(page==='assets'"
if html.count(permission_marker)!=1:
    raise SystemExit(f'Unexpected navigate permission marker count: {html.count(permission_marker)}')
html=html.replace(permission_marker,permission_replacement,1)

# Initial hash restoration and later hash changes must resolve the client scope
# before assigning currentPage, otherwise Vue can paint the aggregate state for
# one frame and only then synchronize the selected client.
initial_hash="if(allowed.includes(hash)&&this.canViewPage(hash))this.currentPage=hash;"
initial_hash_new="if(allowed.includes(hash)&&this.canViewPage(hash)){this.prepareScopedPageClient(hash);this.currentPage=hash;}"
if html.count(initial_hash)!=1:
    raise SystemExit(f'Unexpected initial hash route marker count: {html.count(initial_hash)}')
html=html.replace(initial_hash,initial_hash_new,1)

hash_change="if(allowed.includes(h)&&this.canViewPage(h)){this.currentPage=h;"
hash_change_new="if(allowed.includes(h)&&this.canViewPage(h)){this.prepareScopedPageClient(h);this.currentPage=h;"
if html.count(hash_change)!=1:
    raise SystemExit(f'Unexpected hashchange route marker count: {html.count(hash_change)}')
html=html.replace(hash_change,hash_change_new,1)

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
if html.count(old_method)!=1:
    raise SystemExit(f'Unexpected openClientDetail method count: {html.count(old_method)}')
html=html.replace(old_method,new_method,1)

old_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
new_back='<button type="button" @click="returnFromClientDetail()" class="w-10 h-10 rounded-xl border border-slate-200 bg-white" title="返回上一来源页面"><i class="fa-solid fa-arrow-left"></i></button>'
if html.count(old_back)!=1:
    raise SystemExit(f'Unexpected client-detail fixed back button count: {html.count(old_back)}')
html=html.replace(old_back,new_back,1)

old_assets_detail='<button v-if="selectedAssetsClient && selectedAssetsClientId!==0" @click="openClientDetail(selectedAssetsClient.id)"'
new_assets_detail='<button v-if="selectedAssetsClient && selectedAssetsClientId!==0" @click="openClientDetail(selectedAssetsClient.id,\'assets\')"'
if html.count(old_assets_detail)!=1:
    raise SystemExit(f'Unexpected aggregate-aware account-assets detail shortcut count: {html.count(old_assets_detail)}')
html=html.replace(old_assets_detail,new_assets_detail,1)

# Cloud/session hash restoration is another direct currentPage writer.  Make it
# use the same pre-render scope resolver before exposing the target page.
old_adapter_route="if(allowed.includes(h)&&vm.canViewPage(h))vm.currentPage=h;"
new_adapter_route="if(allowed.includes(h)&&vm.canViewPage(h)){vm.prepareScopedPageClient?.(h);vm.currentPage=h;}"
if adapter.count(old_adapter_route)!=1:
    raise SystemExit(f'Unexpected cloud adapter route marker count: {adapter.count(old_adapter_route)}')
adapter=adapter.replace(old_adapter_route,new_adapter_route,1)

# The native UI action bridge runs in capture phase and previously swallowed the
# Vue back click, forcing every client-detail arrow to the client list. Patch the
# actual browser runtime so it honors the same remembered source as the Vue method.
old_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','client-form','client-detail']);"
new_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','assets','client-form','client-detail']);"
if bridge.count(old_scroll_pages)!=1:
    raise SystemExit(f'Unexpected UI bridge scroll page set count: {bridge.count(old_scroll_pages)}')
bridge=bridge.replace(old_scroll_pages,new_scroll_pages,1)

# Any bridge-driven navigation must also resolve the scoped client before it
# assigns currentPage. This prevents runtime helpers from bypassing Vue's
# pre-render selection order.
bridge_source="""  const navigateWithPageScroll=(page,sourceHint)=>{
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage,sourceHint);"""
bridge_source_new="""  const navigateWithPageScroll=(page,sourceHint)=>{
    const sourcePage=vm.currentPage;
    if(page!==sourcePage)vm.prepareScopedPageClient?.(page);
    if(sourcePage)rememberPageScroll(sourcePage,sourceHint);"""
if bridge.count(bridge_source)!=1:
    raise SystemExit(f'Unexpected UI bridge navigation marker count: {bridge.count(bridge_source)}')
bridge=bridge.replace(bridge_source,bridge_source_new,1)

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
if bridge.count(old_finalize)!=1:
    raise SystemExit(f'Unexpected UI bridge client-list finalizer count: {bridge.count(old_finalize)}')
bridge=bridge.replace(old_finalize,new_finalize,1)

old_runtime_back="if(button.querySelector('i.fa-arrow-left'))bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button));"
new_runtime_back="if(button.querySelector('i.fa-arrow-left'))bind(button,'client-detail-back',button=>returnFromClientDetailBridge(button));"
if bridge.count(old_runtime_back)!=1:
    raise SystemExit(f'Unexpected UI bridge hard-coded detail back count: {bridge.count(old_runtime_back)}')
bridge=bridge.replace(old_runtime_back,new_runtime_back,1)

old_save_return='            finalizeClientListNavigation();'
new_save_return='            finalizeClientSaveNavigation();'
if bridge.count(old_save_return)!=1:
    raise SystemExit(f'Unexpected UI bridge client save return count: {bridge.count(old_save_return)}')
bridge=bridge.replace(old_save_return,new_save_return,1)

index_path.write_text(html,encoding='utf-8')
bridge_path.write_text(bridge,encoding='utf-8')
adapter_path.write_text(adapter,encoding='utf-8')
print('CLIENT_DETAIL_RETURN_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; bridge='+hashlib.sha256(bridge_path.read_bytes()).hexdigest()+'; adapter='+hashlib.sha256(adapter_path.read_bytes()).hexdigest())
print('SCOPED_PAGE_NAVIGATION_FINALIZE_OK: assets=preselected; ads=preselected; sop=preselected')
