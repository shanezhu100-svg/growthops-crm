from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "navigateToModuleHome(page){",
    "this.navigateTo(page);",
    "if(page==='assets')this.selectedAssetsClientId=0;",
    "else if(page==='ads')this.selectedAdsClientId=0;",
    "else if(page==='analytics')this.selectedAnalyticsClientId=0;",
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

require('navigateToModuleHome(' in html,'module-home wrapper is unused')
require('@click="navigateToModuleHome(' in html,'module navigation click binding missing')
require('<option :value="0">全部客户</option>' in html,
        'account-assets all-client option must remain available')
require('prepareScopedPageClient(page)' not in html,
        'reverted scoped preselection must not be restored')
require("returnFromClientDetail(){" in html,'client-detail return logic missing')
require("sessionStorage.getItem('growthops_client_detail_return_page')" in html,
        'client-detail source persistence missing')

print(
    'MODULE_HOME_NAVIGATION_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
