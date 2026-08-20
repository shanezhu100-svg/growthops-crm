from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "showAllClientsForModule(page){",
    "if(page==='assets')this.selectedAssetsClientId=0;",
    "else if(page==='ads')this.selectedAdsClientId=0;",
    "else if(page==='analytics')this.selectedAnalyticsClientId=0;",
    'id="growthops-module-home-navigation-style"',
    'data-growthops-module-home="analytics"',
    'data-growthops-module-home="ads"',
    'data-growthops-module-home="assets"',
    '@click="showAllClientsForModule(\'analytics\')"',
    '@click="showAllClientsForModule(\'ads\')"',
    '@click="showAllClientsForModule(\'assets\')"',
    '@keydown.enter.prevent="showAllClientsForModule(\'analytics\')"',
    '@keydown.enter.prevent="showAllClientsForModule(\'ads\')"',
    '@keydown.enter.prevent="showAllClientsForModule(\'assets\')"',
):
    require(marker in html,f'module-home marker missing: {marker}')

for marker in (
    "const MODULE_HOME_NAV_LABELS=new Map([",
    "['账号与商业资产','assets']",
    "['广告管理','ads']",
    "['投放数据分析','analytics']",
    "control.closest('aside')",
    "const page=MODULE_HOME_NAV_LABELS.get(text(control));",
    "queueMicrotask(()=>{",
    "if(vm.currentPage!==page)return;",
    "vm.showAllClientsForModule?.(page);",
):
    require(marker in bridge,f'module-home bridge marker missing: {marker}')

bridge_start=bridge.find("const MODULE_HOME_NAV_LABELS=new Map([")
bridge_end=bridge.find("  const protectPendingSave=event=>{",bridge_start)
require(bridge_start>=0 and bridge_end>bridge_start,'unable to bound module-home bridge block')
module_bridge=bridge[bridge_start:bridge_end]
require('stopImmediatePropagation' not in module_bridge,
        'module-home sidebar listener must not swallow native navigation')
require('preventDefault' not in module_bridge,
        'module-home sidebar listener must not cancel native navigation')

require('<option :value="0">全部客户</option>' in html,
        'account-assets all-client option must remain available')
require('prepareScopedPageClient(page)' not in html,
        'reverted scoped preselection must not be restored')
require("returnFromClientDetail(){" in html,'client-detail return logic missing')
require("sessionStorage.getItem('growthops_client_detail_return_page')" in html,
        'client-detail source persistence missing')

print(
    'MODULE_HOME_NAVIGATION_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'bridge={hashlib.sha256(bridge_path.read_bytes()).hexdigest()}'
)
