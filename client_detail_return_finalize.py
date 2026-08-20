from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')

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

# The native UI action bridge runs in capture phase and previously swallowed the
# Vue back click, forcing every client-detail arrow to the client list. Patch the
# actual browser runtime so it honors the same remembered source as the Vue method.
old_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','client-form','client-detail']);"
new_scroll_pages="const PAGE_SCROLL_PAGES=new Set(['clients','assets','client-form','client-detail']);"
if bridge.count(old_scroll_pages)!=1:
    raise SystemExit(f'Unexpected UI bridge scroll page set count: {bridge.count(old_scroll_pages)}')
bridge=bridge.replace(old_scroll_pages,new_scroll_pages,1)

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
print('CLIENT_DETAIL_RETURN_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; bridge='+hashlib.sha256(bridge_path.read_bytes()).hexdigest())
