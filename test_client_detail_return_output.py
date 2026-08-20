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
    "sessionStorage.setItem('growthops_client_detail_return_page',source)",
    "returnFromClientDetail(){",
    "sessionStorage.getItem('growthops_client_detail_return_page')",
    "@click=\"returnFromClientDetail()\"",
    "@click=\"openClientDetail(selectedAssetsClient.id,'assets')\"",
):
    require(marker in html,f'client detail source-aware marker missing: {marker}')

require("bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button))" not in bridge,
        'runtime bridge must not force client-detail back to clients')
require('finalizeClientListNavigation();' not in bridge,
        'client edit save bridge must not force navigation to clients')

# One authoritative pre-render resolver owns assets / ads / SOP entry.
for marker in (
    "prepareScopedPageClient(page){",
    "const scopedPages=new Set(['assets','ads','sop']);",
    "if(!scopedPages.has(page)||page===this.currentPage)return;",
    "if(!text||text==='0'||text.toUpperCase()==='ALL')return null;",
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
    require(marker in html,f'scoped pre-render marker missing: {marker}')

# “全部客户” is still an explicit user option, not removed to hide the symptom.
require('<option :value="0">全部客户</option>' in html,
        'account-assets all-client option must remain available')

nav_start=html.find('    navigateTo(page){')
nav_end=html.find("    openClientDetail(id,sourcePage='')",nav_start)
require(nav_start>=0 and nav_end>nav_start,'unable to bound navigateTo')
nav_block=html[nav_start:nav_end]
prepare_pos=nav_block.find('this.prepareScopedPageClient(page);')
render_pos=nav_block.find('this.currentPage=page;')
require(prepare_pos>=0 and render_pos>=0 and prepare_pos<render_pos,
        'navigateTo must resolve client scope before currentPage render')

# If canonical mounted hash writers still exist in the final build, they must also
# be preceded by the resolver. Earlier finalizers are allowed to remove them.
if 'this.currentPage=hash' in html:
    require('this.prepareScopedPageClient(hash);this.currentPage=hash' in html,
            'surviving initial hash writer must prepare client scope first')
if 'this.currentPage=h' in html:
    require('this.prepareScopedPageClient(h);this.currentPage=h' in html,
            'surviving hashchange writer must prepare client scope first')

# Cloud/session routing is mandatory and must prepare before exposing the route.
require("if(allowed.includes(h)&&vm.canViewPage(h)){vm.prepareScopedPageClient?.(h);vm.currentPage=h;}" in adapter,
        'cloud routeFromHash must prepare client scope before currentPage')
require("if(allowed.includes(h)&&vm.canViewPage(h))vm.currentPage=h;" not in adapter,
        'legacy cloud direct route writer must not survive')

# Capture-phase bridge is also mandatory and must not bypass Vue ordering.
for marker in (
    "const PAGE_SCROLL_PAGES=new Set(['clients','assets','client-form','client-detail']);",
    "if(page!==sourcePage)vm.prepareScopedPageClient?.(page);",
    "const CLIENT_DETAIL_RETURN_KEY='growthops_client_detail_return_page';",
    "const returnFromClientDetailBridge=button=>{",
    "bind(button,'client-detail-back',button=>returnFromClientDetailBridge(button))",
    "const finalizeClientSaveNavigation=()=>navigateWithPageScroll('client-detail');",
):
    require(marker in bridge,f'runtime navigation marker missing: {marker}')

bridge_start=bridge.find('  const navigateWithPageScroll=(page,sourceHint)=>{')
bridge_end=bridge.find('  const CLIENT_DETAIL_RETURN_KEY=',bridge_start)
require(bridge_start>=0 and bridge_end>bridge_start,'unable to bound runtime bridge navigation')
bridge_block=bridge[bridge_start:bridge_end]
bridge_prepare=bridge_block.find('vm.prepareScopedPageClient?.(page);')
bridge_render=bridge_block.find('vm.currentPage=page;')
require(bridge_prepare>=0 and bridge_render>=0 and bridge_prepare<bridge_render,
        'runtime bridge must prepare client scope before currentPage')

index_sha=hashlib.sha256(index_path.read_bytes()).hexdigest()
bridge_sha=hashlib.sha256(bridge_path.read_bytes()).hexdigest()
adapter_sha=hashlib.sha256(adapter_path.read_bytes()).hexdigest()
print(f'CLIENT_DETAIL_RETURN_OUTPUT_TESTS_OK: index={index_sha}; bridge={bridge_sha}; adapter={adapter_sha}')
print('SCOPED_PAGE_NAVIGATION_OUTPUT_TESTS_OK: assets=pre-render; ads=pre-render; sop=pre-render')
