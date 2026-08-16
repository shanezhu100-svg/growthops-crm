from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
bridge=(root/'dist'/'cloud-ui-action-bridge.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'native-action-bridge-v17-legacy-method-navigation',
    'invokeLegacyClientNavigate',
    'clientIdForTableRow',
    'clientIdForMobileDetailButton',
    'openClientDetailNative',
    'client-detail-name-open',
    'client-detail-open',
    'client-detail-mobile-open',
    "vm.filteredClients?.[index]?.id",
    "typeof vm.openClientDetail==='function'",
    "typeof vm.navigateTo==='function'",
    'client-form-back',
    'vm.formDirty=false',
    "invokeLegacyClientNavigate(vm.form?.id?'client-detail':'clients')",
    "pageScrollPositions['client-detail']=0",
    'restorePageScrollInstant',
):
    require(marker in bridge,f'client navigation marker missing: {marker}')

require("navigateWithPageScroll(vm.form?.id?'client-detail':'clients')" not in bridge,'client back/cancel still uses complex scroll-memory navigation')
require("if(vm.currentPage==='clients')" in bridge,'client list detail binding scope missing')
require("document.querySelectorAll('tbody tr').forEach" in bridge,'desktop client detail/name buttons are not bridged by table row')
require("text(button)==='查看客户详情'" in bridge,'mobile client detail bridge missing')
require("window.scrollTo=()=>writeScrollTop(targetTop)" in bridge,'legacy back/cancel smooth scroll is not intercepted')
require("window.scrollTo=()=>writeScrollTop(0)" in bridge,'legacy detail smooth scroll is not intercepted')
require("window.scrollTo=originalScrollTo" in bridge,'window.scrollTo is not restored after client navigation')
require("try{vm.$forceUpdate?.()}catch{}" in bridge,'client navigation must force Vue render after native bridge invocation')
require("if(vm.currentPage!=='client-detail')vm.currentPage='client-detail'" in bridge,'client detail fallback render state missing')
require("setPageUrl('client-detail')" in bridge,'client detail URL synchronization missing')

# Save behavior is already user-accepted and must stay untouched by this patch.
client_save=bridge.split("if(label==='保存修改'||label==='确认合作并创建客户')",1)[1]
require('finalizeClientListNavigation();' in client_save,'accepted client save return path was changed')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in client_save,'accepted client cloud save path was changed')
require("vm.persist=()=>{persistRequested=true;return true}" in client_save,'accepted duplicate-save suppression was changed')
require('window.location.reload' not in bridge and 'window.location.replace' not in bridge,'client navigation must remain SPA-only')

print('UI_CLIENT_NAVIGATION_OUTPUT_TESTS_OK: bridge='+hashlib.sha256((root/'dist'/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
