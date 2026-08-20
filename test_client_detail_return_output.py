from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
adapter_path=root/'dist'/'cloud-adapter.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')
adapter=adapter_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

# Client-detail source-aware return remains protected.
for marker in (
    "openClientDetail(id,sourcePage=''){",
    "const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);",
    "const requestedSource=String(sourcePage||'').trim();",
    "const source=allowedSources.has(requestedSource)?requestedSource:(allowedSources.has(currentSource)?currentSource:'clients');",
    "sessionStorage.setItem('growthops_client_detail_return_page',source)",
    "if(source==='assets')this.selectedAssetsClientId=id;",
    "returnFromClientDetail(){",
    "sessionStorage.getItem('growthops_client_detail_return_page')",
    "if(source==='assets'&&this.selectedClientId!==null&&this.selectedClientId!==undefined)this.selectedAssetsClientId=this.selectedClientId;",
    "sessionStorage.removeItem('growthops_client_detail_return_page')",
    "@click=\"returnFromClientDetail()\"",
    "title=\"返回上一来源页面\"",
    "@click=\"openClientDetail(selectedAssetsClient.id,'assets')\"",
):
    require(marker in html,f'client detail explicit-source return marker missing: {marker}')

fixed_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
require(fixed_back not in html,'client detail back button must not remain hard-coded to clients')
require('@click="openClientDetail(selectedAssetsClient.id)"' not in html,'account-assets detail button must pass explicit assets source')
require("this.canViewPage(source)" not in html,'detail return source resolution must not depend on canViewPage(source)')
require("openClientDetail(id){this.selectedClientId=id;" not in html,'legacy source-blind openClientDetail must not survive')

method_start=html.find("    openClientDetail(id,sourcePage=''){")
method_end=html.find('    defaultAssetPagerScope()',method_start)
require(method_start>=0 and method_end>method_start,'unable to bound client detail source-aware methods')
block=html[method_start:method_end]
require("sessionStorage.setItem('growthops_client_detail_return_page',source)" in block,'detail source must survive rerender/edit via sessionStorage')
require("this.navigateTo(source);" in block,'detail return must navigate to preserved source')

# One authoritative pre-render resolver owns assets / ads / SOP navigation.
for marker in (
    "prepareScopedPageClient(page){",
    "const scopedPages=new Set(['assets','ads','sop']);",
    "if(!scopedPages.has(page)||page===this.currentPage)return;",
    "if(this.currentPage==='assets')sourceId=resolvedId(this.selectedAssetsClientId);",
    "else if(this.currentPage==='ads')sourceId=resolvedId(this.selectedAdsClientId);",
    "else if(this.currentPage==='sop')sourceId=resolvedId(this.selectedSopClientId);",
    "const preferred=sourceId??ownId??resolvedId(this.selectedClientId)??active[0].id;",
    "this.selectedAssetsClientId=preferred;",
    "this.selectedAdsClientId=preferred;",
    "this.syncAdsAccountSelection();",
    "this.selectedSopClientId=preferred;",
    "this.syncSopAccountSelection(changed);",
    "this.prepareScopedPageClient(page);if(page==='assets'",
):
    require(marker in html,f'scoped page pre-render marker missing: {marker}')

# Aggregate modes remain available by explicit user choice after the page is open.
require('<option :value="0">全部客户</option>' in html,
        'account-assets explicit all-client option must remain available')
require("if(!text||text==='0'||text.toUpperCase()==='ALL')return null;" in html,
        'transient aggregate sentinel must not win page-entry client resolution')

nav_start=html.find('    navigateTo(page){')
nav_end=html.find("    openClientDetail(id,sourcePage='')",nav_start)
require(nav_start>=0 and nav_end>nav_start,'unable to bound navigateTo method')
nav_block=html[nav_start:nav_end]
prepare_pos=nav_block.find('this.prepareScopedPageClient(page);')
render_pos=nav_block.find('this.currentPage=page;')
require(prepare_pos>=0 and render_pos>=0 and prepare_pos<render_pos,
        'navigateTo must resolve scoped client before assigning currentPage')

# Gate mounted initial hash restoration and hashchange by actual execution order,
# independent of how prior finalizers format the surrounding conditions.
hash_anchor=html.find("const hash=window.location.hash.slice(1);")
hash_listener=html.find("window.addEventListener('hashchange'",hash_anchor)
require(hash_anchor>=0 and hash_listener>hash_anchor,'unable to bound mounted initial hash route')
initial_hash_block=html[hash_anchor:hash_listener]
initial_prepare=initial_hash_block.find('this.prepareScopedPageClient(hash);')
initial_render=initial_hash_block.find('this.currentPage=hash')
require(initial_prepare>=0 and initial_render>=0 and initial_prepare<initial_render,
        'initial hash route must resolve scoped client before currentPage')

hash_end=html.find("window.addEventListener('beforeunload'",hash_listener)
require(hash_end>hash_listener,'unable to bound mounted hashchange route')
hash_block=html[hash_listener:hash_end]
hash_prepare=hash_block.find('this.prepareScopedPageClient(h);')
hash_render=hash_block.find('this.currentPage=h')
require(hash_prepare>=0 and hash_render>=0 and hash_prepare<hash_render,
        'hashchange must resolve scoped client before currentPage')

# Cloud/session hash restoration must use the same resolver before currentPage.
require("if(allowed.includes(h)&&vm.canViewPage(h)){vm.prepareScopedPageClient?.(h);vm.currentPage=h;}" in adapter,
        'cloud routeFromHash must prepare scoped client before currentPage')
require("if(allowed.includes(h)&&vm.canViewPage(h))vm.currentPage=h;" not in adapter,
        'legacy cloud routeFromHash direct render must not survive')

# Runtime bridge is capture-phase and can override Vue handlers. Gate the final
# browser bridge itself so it cannot bypass either return-source or client scope.
for marker in (
    "const PAGE_SCROLL_PAGES=new Set(['clients','assets','client-form','client-detail']);",
    "const CLIENT_DETAIL_RETURN_KEY='growthops_client_detail_return_page';",
    "const CLIENT_DETAIL_RETURN_PAGES=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','account-opening','finance','alerts','tools','system']);",
    "const readClientDetailReturnPage=()=>{",
    "const returnFromClientDetailBridge=button=>{",
    "if(target==='assets'&&vm.selectedClientId!==null&&vm.selectedClientId!==undefined)vm.selectedAssetsClientId=vm.selectedClientId;",
    "bind(button,'client-detail-back',button=>returnFromClientDetailBridge(button))",
    "const finalizeClientSaveNavigation=()=>navigateWithPageScroll('client-detail');",
    "finalizeClientSaveNavigation();",
    "if(page!==sourcePage)vm.prepareScopedPageClient?.(page);",
):
    require(marker in bridge,f'client detail/runtime scoped navigation marker missing: {marker}')

bridge_nav_start=bridge.find('  const navigateWithPageScroll=(page,sourceHint)=>{')
bridge_nav_end=bridge.find('  const CLIENT_DETAIL_RETURN_KEY=',bridge_nav_start)
require(bridge_nav_start>=0 and bridge_nav_end>bridge_nav_start,'unable to bound bridge navigation')
bridge_nav=bridge[bridge_nav_start:bridge_nav_end]
bridge_prepare=bridge_nav.find('vm.prepareScopedPageClient?.(page);')
bridge_render=bridge_nav.find('vm.currentPage=page;')
require(bridge_prepare>=0 and bridge_render>=0 and bridge_prepare<bridge_render,
        'runtime bridge must resolve scoped client before assigning currentPage')

require("bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button))" not in bridge,
        'runtime bridge must not force client-detail back to clients')
require('finalizeClientListNavigation();' not in bridge,
        'client edit save bridge must not force navigation to clients')

index_sha=hashlib.sha256(index_path.read_bytes()).hexdigest()
bridge_sha=hashlib.sha256(bridge_path.read_bytes()).hexdigest()
adapter_sha=hashlib.sha256(adapter_path.read_bytes()).hexdigest()
print('CLIENT_DETAIL_RETURN_OUTPUT_TESTS_OK: index='+index_sha+'; bridge='+bridge_sha+'; adapter='+adapter_sha)
print('SCOPED_PAGE_NAVIGATION_OUTPUT_TESTS_OK: assets=pre-render; ads=pre-render; sop=pre-render')
