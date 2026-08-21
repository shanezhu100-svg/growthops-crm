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
    "navigateToModuleHome(page){",
    "if(this.currentPage==='assets'&&page!=='assets')this.selectedAssetsClientId=0;",
    "if(this.currentPage==='ads'&&page!=='ads')this.selectedAdsClientId=0;",
    "if(page==='assets')this.selectedAssetsClientId=0;",
    "else if(page==='ads')this.selectedAdsClientId=0;",
    "else if(page==='analytics')this.selectedAnalyticsClientId=0;",
    "this.navigateTo(page);",
    '@click="navigateToModuleHome(item.key)"',
    '@click="navigateToModuleHome(item.key); mobileMenuOpen=false"',
    'id="growthops-module-home-navigation-style"',
    'data-growthops-module-home="analytics"',
    'data-growthops-module-home="ads"',
    'data-growthops-module-home="assets"',
    '@click="navigateToModuleHome(\'analytics\')"',
    '@click="navigateToModuleHome(\'ads\')"',
    '@click="navigateToModuleHome(\'assets\')"',
    '@keydown.enter.prevent="navigateToModuleHome(\'analytics\')"',
    '@keydown.enter.prevent="navigateToModuleHome(\'ads\')"',
    '@keydown.enter.prevent="navigateToModuleHome(\'assets\')"',
):
    require(marker in html,f'module-home marker missing: {marker}')

# The canonical sidebar bindings must no longer bypass the module-home method.
require('@click="navigateTo(item.key)"' not in html,
        'desktop sidebar still bypasses module-home navigation')
require('@click="navigateTo(item.key); mobileMenuOpen=false"' not in html,
        'mobile sidebar still bypasses module-home navigation')

# No second runtime bridge handler is allowed for this behavior. This avoids the
# duplicate/capture-order problem that made the prior implementation unreliable.
require('MODULE_HOME_NAV_LABELS' not in bridge,
        'duplicate module-home runtime bridge listener must not survive')
require('showAllClientsForModule' not in bridge,
        'legacy module-home bridge callback must not survive')

# All-client capability itself must remain intact, and previous scoped preselection
# must stay reverted.
require('<option :value="0">全部客户</option>' in html,
        'account-assets all-client option must remain available')
require('v-if="selectedAssetsClientId===0"' in html,
        'account-assets aggregate view must remain keyed to sentinel 0')
require("selectedAnalyticsClient(){if(Number(this.selectedAnalyticsClientId)===0)return null;" in html,
        'analytics all-client sentinel must remain supported')
require("selectedAdsClient(){if(Number(this.selectedAdsClientId)===0)return null;" in html,
        'ads all-client sentinel must remain supported')
require('prepareScopedPageClient(page)' not in html,
        'reverted scoped preselection must not be restored')

# Previously fixed client-detail source-aware return must remain intact.
require("returnFromClientDetail(){" in html,'client-detail return logic missing')
require("sessionStorage.getItem('growthops_client_detail_return_page')" in html,
        'client-detail source persistence missing')

# Ordering guard: leaving assets/ads through top-level navigation first stores
# each module back to all-client mode, and target-module selectors reset before
# normal navigation executes.
start=html.find('    navigateToModuleHome(page){')
end=html.find('    navigateTo(page){',start)
require(start>=0 and end>start,'unable to bound module-home method')
block=html[start:end]
nav_pos=block.find('this.navigateTo(page);')
for leave_reset in (
    "if(this.currentPage==='assets'&&page!=='assets')this.selectedAssetsClientId=0;",
    "if(this.currentPage==='ads'&&page!=='ads')this.selectedAdsClientId=0;",
):
    leave_pos=block.find(leave_reset)
    require(leave_pos>=0 and leave_pos<nav_pos,
            f'module leave reset must execute before navigation: {leave_reset}')
for assignment in (
    "if(page==='assets')this.selectedAssetsClientId=0;",
    "this.selectedAdsClientId=0;",
    "this.selectedAnalyticsClientId=0;",
):
    pos=block.find(assignment)
    require(pos>=0 and pos<nav_pos,
            f'module-home selector must reset before navigation: {assignment}')

print(
    'MODULE_HOME_NAVIGATION_OUTPUT_TESTS_OK: authoritative=vue-sidebar; assets-return=all-clients; ads-return=all-clients; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'bridge={hashlib.sha256(bridge_path.read_bytes()).hexdigest()}'
)
