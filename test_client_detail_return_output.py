from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "openClientDetail(id,sourcePage=''){",
    "const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','opening','finance','alerts','settings']);",
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

print('CLIENT_DETAIL_RETURN_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest())
