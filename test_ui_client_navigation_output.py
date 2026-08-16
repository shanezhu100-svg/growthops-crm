from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
bridge=(root/'dist'/'cloud-ui-action-bridge.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'native-action-bridge-v18-root-client-capture',
    '__GROWTHOPS_ROOT_CLIENT_CAPTURE_V18__',
    'rawClientMethods',
    'rawClientNavigate',
    'rootNavigateClientPage',
    'rootClientCapture',
    "window.addEventListener('click',rootClientCapture,true)",
    "event.target?.closest?.('button')",
    "label==='详情'||label==='查看客户详情'||button===nameButton",
    "vm.currentPage==='clients'",
    "vm.currentPage==='client-form'",
    "vm.selectedClientId=clientId",
    "vm.credentialsVisible=false",
    "vm.resetAssetPager?.('detail')",
    "rootNavigateClientPage('client-detail',0)",
    "label==='取消'||!!button.querySelector('i.fa-arrow-left')",
    'vm.formDirty=false',
    "const target=vm.form?.id?'client-detail':'clients'",
    'event.stopImmediatePropagation()',
    'rootClientCapture=true',
):
    require(marker in bridge,f'root client navigation marker missing: {marker}')

require("rawClientNavigate.call(vm,page)" in bridge,'root navigation must invoke original Vue component navigateTo method')
require("button.closest('.fixed.inset-0.modal-backdrop')" in bridge,'client-form root capture must not hijack modal cancel buttons')
require("window.location.reload" not in bridge and "window.location.replace" not in bridge,'client navigation must remain SPA-only')

# Save behavior is already user-accepted and must remain outside the root capture patch.
client_save=bridge.split("if(label==='保存修改'||label==='确认合作并创建客户')",1)[1]
require('finalizeClientListNavigation();' in client_save,'accepted client save return path was changed')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in client_save,'accepted client cloud save path was changed')
require("vm.persist=()=>{persistRequested=true;return true}" in client_save,'accepted duplicate-save suppression was changed')
require("label==='保存修改'" not in bridge.split('const rootClientCapture=event=>',1)[1].split("if(!window[ROOT_CLIENT_CAPTURE])",1)[0], 'root capture must not intercept accepted save button path')

print('UI_CLIENT_NAVIGATION_OUTPUT_TESTS_OK: bridge='+hashlib.sha256((root/'dist'/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
