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

# The old wrapper implementation was the bug: it wrote sentinel 0 and then
# navigateTo() treated that 0 as an invalid client and replaced it. It must not
# survive anywhere in final browser output.
require('navigateToModuleHome(' not in html,
        'legacy module-home wrapper must not survive')
require("if(this.currentPage==='assets'&&page!=='assets')this.selectedAssetsClientId=0;" not in html,
        'legacy assets leave-reset must not survive')
require("if(this.currentPage==='ads'&&page!=='ads')this.selectedAdsClientId=0;" not in html,
        'legacy ads leave-reset must not survive')

for marker in (
    "navigateTo(page,moduleHome=false){",
    "if(moduleHome){if(page==='assets')this.selectedAssetsClientId=0;else if(page==='ads')this.selectedAdsClientId=0;else if(page==='analytics')this.selectedAnalyticsClientId=0;}",
    "if(page==='assets'&&Number(this.selectedAssetsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAssetsClientId))this.selectedAssetsClientId=this.clients[0]?.id||null;",
    "if(page==='analytics'){if(Number(this.selectedAnalyticsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAnalyticsClientId))this.selectedAnalyticsClientId=this.clients[0]?.id||null;this.syncAnalyticsAccountSelection()}",
    "if(page==='ads'){if(Number(this.selectedAdsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAdsClientId))this.selectedAdsClientId=this.clients[0]?.id||null;this.syncAdsAccountSelection()}",
    '@click="navigateTo(item.key,true)"',
    '@click="navigateTo(item.key,true); mobileMenuOpen=false"',
    'id="growthops-module-home-navigation-style"',
    'data-growthops-module-home="analytics"',
    'data-growthops-module-home="ads"',
    'data-growthops-module-home="assets"',
    '@click="navigateTo(\'analytics\',true)"',
    '@click="navigateTo(\'ads\',true)"',
    '@click="navigateTo(\'assets\',true)"',
    '@keydown.enter.prevent="navigateTo(\'analytics\',true)"',
    '@keydown.enter.prevent="navigateTo(\'ads\',true)"',
    '@keydown.enter.prevent="navigateTo(\'assets\',true)"',
):
    require(marker in html,f'module-home marker missing: {marker}')

# The exact old validation that overwrote sentinel 0 must be gone for all three
# aggregate-capable modules.
require("if(page==='assets'&&!this.clients.some(c=>c.id===this.selectedAssetsClientId))" not in html,
        'assets navigation still rejects aggregate sentinel 0')
require("if(page==='analytics'){if(!this.clients.some(c=>c.id===this.selectedAnalyticsClientId))" not in html,
        'analytics navigation still rejects aggregate sentinel 0')
require("if(page==='ads'){if(!this.clients.some(c=>c.id===this.selectedAdsClientId))" not in html,
        'ads navigation still rejects aggregate sentinel 0')

# No second runtime bridge handler is allowed for this behavior.
require('MODULE_HOME_NAV_LABELS' not in bridge,
        'duplicate module-home runtime bridge listener must not survive')
require('showAllClientsForModule' not in bridge,
        'legacy module-home bridge callback must not survive')

# All-client capability itself must remain intact.
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

# Previously fixed client-detail source-aware return must remain intact. Its
# internal navigateTo(source) call intentionally does not pass moduleHome=true.
require("returnFromClientDetail(){" in html,'client-detail return logic missing')
require("sessionStorage.getItem('growthops_client_detail_return_page')" in html,
        'client-detail source persistence missing')
require("this.navigateTo(source);" in html,
        'client-detail return must preserve source context')

# Regression guard for the original failure: in the real navigateTo() method the
# module-home reset must happen before the stale-client validation, and that
# validation must explicitly exempt sentinel 0. This proves 0 survives the full
# navigateTo path instead of only proving that it was assigned beforehand.
start=html.find('    navigateTo(page,moduleHome=false){')
end=html.find('    openClientDetail(',start)
require(start>=0 and end>start,'unable to bound authoritative navigateTo method')
block=html[start:end]
module_home_pos=block.find('if(moduleHome){')
require(module_home_pos>=0,'module-home reset missing from navigateTo')
for reset,guard in (
    ("if(page==='assets')this.selectedAssetsClientId=0;",
     "if(page==='assets'&&Number(this.selectedAssetsClientId)!==0"),
    ("else if(page==='ads')this.selectedAdsClientId=0;",
     "if(page==='ads'){if(Number(this.selectedAdsClientId)!==0"),
    ("else if(page==='analytics')this.selectedAnalyticsClientId=0;",
     "if(page==='analytics'){if(Number(this.selectedAnalyticsClientId)!==0"),
):
    reset_pos=block.find(reset)
    guard_pos=block.find(guard)
    require(reset_pos>=0 and guard_pos>=0,
            f'cannot verify sentinel flow: {reset} / {guard}')
    require(reset_pos<guard_pos,
            f'aggregate sentinel must be assigned before validation: {reset}')

print(
    'MODULE_HOME_NAVIGATION_OUTPUT_TESTS_OK: authority=navigateTo; sentinel-zero=valid-through-navigation; wrappers=removed; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'bridge={hashlib.sha256(bridge_path.read_bytes()).hexdigest()}'
)
