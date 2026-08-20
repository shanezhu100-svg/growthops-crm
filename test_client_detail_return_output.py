from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "const source=String(this.currentPage||'');",
    "this.clientDetailReturnPage=(source&&source!=='client-detail'&&source!=='client-form'&&this.canViewPage(source))?source:'clients';",
    "if(this.clientDetailReturnPage==='assets')this.selectedAssetsClientId=id;",
    "returnFromClientDetail(){",
    "const target=(source&&source!=='client-detail'&&source!=='client-form'&&this.canViewPage(source))?source:'clients';",
    "if(target==='assets'&&this.selectedClientId!==null&&this.selectedClientId!==undefined)this.selectedAssetsClientId=this.selectedClientId;",
    "@click=\"returnFromClientDetail()\"",
    "title=\"返回上一来源页面\"",
):
    require(marker in html,f'client detail source-aware return marker missing: {marker}')

fixed_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
require(fixed_back not in html,'client detail back button must not remain hard-coded to clients')
require("openClientDetail(id){this.selectedClientId=id;" not in html,'legacy source-blind openClientDetail must not survive')

# Editing from detail and saving back to detail must not overwrite the remembered source.
# The source is cleared only when the user actually invokes the detail back action.
method_start=html.find('    returnFromClientDetail(){')
method_end=html.find('    defaultAssetPagerScope()',method_start)
require(method_start>=0 and method_end>method_start,'unable to bound client detail return methods')
block=html[method_start:method_end]
require("this.clientDetailReturnPage='';" in block,'detail return source must be cleared after use')
require("this.navigateTo(target);" in block,'detail return must navigate to resolved source')

print('CLIENT_DETAIL_RETURN_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest())
