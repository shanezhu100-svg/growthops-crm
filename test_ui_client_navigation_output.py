from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
bridge=(root/'dist'/'cloud-ui-action-bridge.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'native-action-bridge-v16-client-native-navigation',
    'directClientNavigate',
    'clientIdForDetailButton',
    'openClientDetailNative',
    'client-detail-open',
    "label==='详情'||label==='查看客户详情'",
    "vm.filteredClients?.[index]?.id",
    "typeof vm.openClientDetail==='function'",
    "directClientNavigate('client-detail')",
    'client-form-back',
    'vm.formDirty=false',
    "directClientNavigate(vm.form?.id?'client-detail':'clients')",
):
    require(marker in bridge,f'client navigation marker missing: {marker}')

require("navigateWithPageScroll(vm.form?.id?'client-detail':'clients')" not in bridge,'client back/cancel still uses complex scroll-memory navigation')
require("if(vm.currentPage==='clients')" in bridge,'client list detail binding scope missing')
require("const originalNavigate=vm.navigateTo;" in bridge,'detail open must suppress legacy smooth navigation while initializing selected client')
require("vm.navigateTo=()=>true;" in bridge,'detail open must suppress legacy smooth navigation')
require("vm.navigateTo=originalNavigate" in bridge,'detail open must restore legacy navigation method')

# Save behavior is already user-accepted and must stay untouched by this patch.
client_save=bridge.split("if(label==='保存修改'||label==='确认合作并创建客户')",1)[1]
require('finalizeClientListNavigation();' in client_save,'accepted client save return path was changed')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in client_save,'accepted client cloud save path was changed')
require("vm.persist=()=>{persistRequested=true;return true}" in client_save,'accepted duplicate-save suppression was changed')
require('window.location.reload' not in bridge and 'window.location.replace' not in bridge,'client navigation must remain SPA-only')

print('UI_CLIENT_NAVIGATION_OUTPUT_TESTS_OK: bridge='+hashlib.sha256((root/'dist'/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
