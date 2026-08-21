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
    "if(moduleHome){if(page==='assets')this.selectedAssetsClientId=0;else if(page==='ads')this.selectedAdsClientId=0;else if(page==='analytics')this.selectedAnalyticsClientId=0;else if(page==='sop')this.selectedSopClientId=0;}",
    "if(page==='assets'&&Number(this.selectedAssetsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAssetsClientId))this.selectedAssetsClientId=this.clients[0]?.id||null;",
    "if(page==='analytics'){if(Number(this.selectedAnalyticsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAnalyticsClientId))this.selectedAnalyticsClientId=this.clients[0]?.id||null;this.syncAnalyticsAccountSelection()}",
    "if(page==='ads'){if(Number(this.selectedAdsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAdsClientId))this.selectedAdsClientId=this.clients[0]?.id||null;this.syncAdsAccountSelection()}",
    '@click="navigateTo(item.key,true)"',
    '@click="navigateTo(item.key,true); mobileMenuOpen=false"',
    'id="growthops-module-home-navigation-style"',
    'data-growthops-module-home="analytics"',
    'data-growthops-module-home="ads"',
    'data-growthops-module-home="assets"',
    'data-growthops-module-home="sop"',
    '@click="navigateTo(\'analytics\',true)"',
    '@click="navigateTo(\'ads\',true)"',
    '@click="navigateTo(\'assets\',true)"',
    '@click="navigateTo(\'sop\',true)"',
    '@keydown.enter.prevent="navigateTo(\'analytics\',true)"',
    '@keydown.enter.prevent="navigateTo(\'ads\',true)"',
    '@keydown.enter.prevent="navigateTo(\'assets\',true)"',
    '@keydown.enter.prevent="navigateTo(\'sop\',true)"',
):
    require(marker in html,f'module-home marker missing: {marker}')

# The exact old validation that overwrote sentinel 0 must be gone for the three
# modules that have concrete-client fallback validation.
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

# Existing all-client capability must remain intact.
require('<option :value="0">全部客户</option>' in html,
        'account-assets all-client option must remain available')
require('v-if="selectedAssetsClientId===0"' in html,
        'account-assets aggregate view must remain keyed to sentinel 0')
require("selectedAnalyticsClient(){if(Number(this.selectedAnalyticsClientId)===0)return null;" in html,
        'analytics all-client sentinel must remain supported')
require("selectedAdsClient(){if(Number(this.selectedAdsClientId)===0)return null;" in html,
        'ads all-client sentinel must remain supported')

# SOP must be a real all-client landing page and, after choosing one client,
# expose all executable FB/TikTok accounts directly in the page. The account
# dropdown remains only as a fast switch, not the only way to discover accounts.
for marker in (
    '<option :value="0">所有客户</option><option v-for="c in activeClients" :value="c.id" :key="c.id">{{ c.name }}</option>',
    'v-if="selectedSopClientId===0"',
    '所有客户每日 SOP',
    'sopAllClientRows(){',
    'sopAllAccountCount(){',
    'sopAllConfiguredAccountCount(){',
    'sopAllTodayTaskCount(){',
    '@click="selectedSopClientId=row.client.id; syncSopAccountSelection(true)"',
    '<div v-else-if="selectedSopClient && selectedSopAccount" class="space-y-5">',
    '<div class="font-extrabold text-sm text-slate-900">选择执行账号</div>',
    '@click="selectedSopAccountKey=item.key; onSopAccountChange()"',
    "item.platform==='FB'?'fa-brands fa-facebook':'fa-brands fa-tiktok'",
    "{{ item.platform==='FB' ? 'BM ID' : 'BC ID' }}",
    '进入 Checklist',
    '@click="openClientDetail(selectedSopClient.id,\'sop\')"',
):
    require(marker in html,f'SOP all-client/account-option marker missing: {marker}')
require('<option :value="null">请选择客户</option>' not in html,
        'SOP selector still exposes legacy blank landing state')
require('请在右上角明确选择本次执行账号。' not in html,
        'SOP still contains legacy dropdown-only account chooser')
require("selectedSopClient(){return this.clients.find(c=>!c.archived&&String(c.id)===String(this.selectedSopClientId))||null}" in html,
        'SOP concrete-client computed behavior changed unexpectedly')
require('prepareScopedPageClient(page)' not in html,
        'reverted scoped preselection must not be restored')

# The visible SOP chooser has one canonical card implementation, grouped by
# Facebook and TikTok. There must be no older mixed-grid card implementation in
# this chooser; the top-right select may still iterate all accounts as a switch.
chooser_start_marker='          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="space-y-4">'
chooser_end_marker='          <div v-else-if="selectedSopClient" class="bg-white border border-slate-200 rounded-2xl py-16 text-center text-xs text-slate-400">'
chooser_start=html.find(chooser_start_marker)
chooser_end=html.find(chooser_end_marker,chooser_start)
require(chooser_start>=0 and chooser_end>chooser_start,'unable to bound final SOP account chooser')
chooser=html[chooser_start:chooser_end]
for marker in (
    'data-sop-platform-groups',
    ':data-sop-platform-group="platformGroup.key"',
    "[{key:'FB',name:'Facebook',icon:'fa-brands fa-facebook'},{key:'TK',name:'TikTok',icon:'fa-brands fa-tiktok'}]",
    '{{ platformGroup.name }} 账号',
    'selectedSopAccounts.filter(item=>item.platform===platformGroup.key).length',
    'v-for="item in selectedSopAccounts.filter(item=>item.platform===platformGroup.key)"',
    '暂无 {{ platformGroup.name }} 可执行账号',
    'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-3',
    'mt-3 grid grid-cols-2 gap-2 text-[10px]',
    'p-3.5 hover:border-indigo-300',
):
    require(marker in chooser,f'grouped SOP chooser marker missing: {marker}')
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5' not in chooser,
        'legacy three-column mixed SOP account grid must not survive')
require('v-for="item in selectedSopAccounts"' not in chooser,
        'legacy mixed SOP account card iteration must not survive')
require('v-for="item in selectedSopAccounts"' in html,
        'top-right SOP account select should remain available as a fast switch')

# Previously fixed client-detail source-aware return must remain intact. Its
# internal navigateTo(source) call intentionally does not pass moduleHome=true.
require("returnFromClientDetail(){" in html,'client-detail return logic missing')
require("sessionStorage.getItem('growthops_client_detail_return_page')" in html,
        'client-detail source persistence missing')
require("this.navigateTo(source);" in html,
        'client-detail return must preserve source context')

# Regression guard for the original failure: in the real navigateTo() method the
# module-home reset must happen before stale-client validation. For SOP there is
# no stale-client fallback; sentinel 0 must be assigned before the existing SOP
# account synchronizer runs, proving module-home navigation reaches aggregate mode.
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

sop_reset=block.find("else if(page==='sop')this.selectedSopClientId=0;")
sop_sync=block.rfind("if(page==='sop')this.syncSopAccountSelection()")
require(sop_reset>=0 and sop_sync>=0,
        'cannot verify SOP aggregate sentinel through navigateTo')
require(sop_reset<sop_sync,
        'SOP aggregate sentinel must be assigned before account synchronization')
require("this.selectedSopClientId=this.clients[0]" not in block,
        'SOP navigateTo must not replace all-client sentinel with first client')

print(
    'MODULE_HOME_NAVIGATION_OUTPUT_TESTS_OK: authority=navigateTo; sentinel-zero=valid-through-navigation; wrappers=removed; sop=all-clients+grouped-account-options; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'bridge={hashlib.sha256(bridge_path.read_bytes()).hexdigest()}'
)
