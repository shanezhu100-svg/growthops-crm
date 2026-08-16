from pathlib import Path
import hashlib
root=Path(__file__).resolve().parent
dist=root/'dist'
html=(dist/'index.html').read_text(encoding='utf-8')
bridge=(dist/'cloud-ui-action-bridge.js').read_text(encoding='utf-8')
anchor=(dist/'client-scroll-anchor-bridge.js').read_text(encoding='utf-8')
transition=(dist/'client-view-transition-bridge.js').read_text(encoding='utf-8')

def require(c,m):
    if not c: raise SystemExit(m)

security='<script src="/cloud-security-hotfix.js"></script>'
tag='<script src="/cloud-ui-action-bridge.js"></script>'
anchor_tag='<script src="/client-scroll-anchor-bridge.js"></script>'
transition_tag='<script src="/client-view-transition-bridge.js"></script>'
require(html.count(tag)==1,'UI action bridge tag missing or duplicated')
require(html.count(anchor_tag)==1,'client scroll anchor bridge tag missing or duplicated')
require(html.count(transition_tag)==1,'client view transition bridge tag missing or duplicated')
require(security+tag+anchor_tag+transition_tag in html,'client bridges must load immediately after security hotfix in stable order')
for marker in ('growthops-session-restore-style','growthops-session-restore-guard','growthops-session-restoring','正在恢复登录会话','growthops_crm_token_v2'):
    require(marker in html,f'session restore guard missing: {marker}')
for marker in (
    'saveOpeningDeal','saveOpeningProvider','saveAdDataRecord','showOpeningModal','showProviderModal','showAdDataModal',
    'client-form-back','client-form-save','client-detail-back','saveClient','stopImmediatePropagation','modalByButton',
    'native-action-bridge-v18-real-scroll-targets','reportValidity','validateButtonForm','finalizeClientListNavigation',
    'PAGE_SCROLL_PAGES','pageScrollPositions','pageScrollTargets','documentScroller','normalizeScrollTarget',
    'findScrollTarget','scanVisibleScrollTarget','resolvePageScrollTarget','readTargetScrollTop','writeTargetScrollTop',
    'rememberPageScroll','getPageScroll','applyPageScroll','restorePageScrollInstant','navigateWithPageScroll',
    'observePageScroll','routeSwitching','clients','client-form','client-detail','isClientDetailOpenButton','pointerdown',
    'originalOpenClientDetail','scrollRestoration','capture:true','saveNow','window.history.replaceState',
    'clearSessionRestoreCover','pendingClientCloudSaves','trackClientCloudSave','beforeunload','originalNavigate'
):
    require(marker in bridge,f'UI action bridge marker missing: {marker}')

require("new Set(['clients','client-form','client-detail'])" in bridge,'client views must keep separate scroll state')
require("const pageScrollTargets=Object.create(null);" in bridge,'real scroll targets must be stored per page')
require("window.addEventListener('scroll',event=>" in bridge and "{capture:true,passive:true}" in bridge,'scroll listener must capture inner scrolling elements')
require("pageScrollTargets[page]=target;" in bridge,'captured scrolling element must be assigned to the active page')
require("pageScrollPositions[page]=readTargetScrollTop(target);" in bridge,'captured scrollTop must be stored from the real target')
require("lastClientPointerTarget=findScrollTarget(button);" in bridge,'detail entry must resolve the actual client-list scrolling ancestor')
require("rememberPageScroll('clients',lastClientPointerTarget);" in bridge,'client-list position must be captured from its real scrolling element')
require("pageScrollPositions['client-detail']=0;" in bridge,'opening detail from clients must not inherit list scrollTop')
require("pageScrollTargets['client-detail']=lastClientPointerTarget" in bridge,'detail route must start with the known viewport target when it persists across views')
require("const originalOpenClientDetail=vm.openClientDetail;" in bridge,'native client detail navigation must be wrapped')
open_block=bridge.split('const originalOpenClientDetail=vm.openClientDetail;',1)[1].split('function modalByButton',1)[0]
require("const fromClients=vm.currentPage==='clients';" in open_block,'detail wrapper must distinguish client-list entry')
require("routeSwitching=true;" in open_block,'detail switch must suppress inherited scroll events before native navigation')
require("originalOpenClientDetail.apply(this,args)" in open_block,'native detail business logic must remain authoritative')
require("restorePageScrollInstant('client-detail',lastClientPointerTarget)" in open_block,'detail must restore its own top after Vue renders')
require("bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button))" in bridge,'detail back must save detail target and restore client-list target')
require("window.history.scrollRestoration='manual'" in bridge,'browser automatic restoration must not compete with SPA restoration')

restore_block=bridge.split('const restorePageScrollInstant=(page,hint)=>',1)[1].split('const navigateWithPageScroll=',1)[0]
require("const targetTop=getPageScroll(page);" in restore_block,'target page scrollTop must be frozen before restoration')
require("routeSwitching=true;" in restore_block and "routeSwitching=false;" in restore_block,'restoration must suppress scroll-memory writes')
require("vm.$nextTick(settle)" in restore_block and "setTimeout(finish,90)" in restore_block,'restoration must wait for Vue and layout settlement')

nav_block=bridge.split('const navigateWithPageScroll=(page,sourceHint)=>',1)[1].split('const finalizeClientListNavigation',1)[0]
require("rememberPageScroll(sourcePage,sourceHint);" in nav_block,'back navigation must capture the source page from its actual scroller')
require(nav_block.index('vm.currentPage=page;') < nav_block.index('applyPageScroll(page,targetTop);'),'destination page must render before fallback target resolution')
require("routeSwitching=true;" in nav_block and "routeSwitching=false;" in nav_block,'explicit navigation must isolate scroll events')

for marker in (
    'client-scroll-anchor-v19-row-position','rowFingerprint','locateAnchorRow','stableClientTokens','captureAnchor',
    'viewportTop','rowIndex','clientId','applyAnchor','scheduleAnchorRestore','setTimeout(run,130)',
    'setTimeout(run,260)','setTimeout(run,520)','__GROWTHOPS_CLIENT_SCROLL_ANCHOR__'
):
    require(marker in anchor,f'client scroll anchor marker missing: {marker}')
require("window.addEventListener('pointerdown',event=>" in anchor,'row anchor must be captured before opening detail')
require("if(vm.currentPage!=='clients')return;" in anchor,'anchor capture must be scoped to client list')
require("const row=button?.closest?.('tbody tr');" in anchor,'clicked customer row must be captured')
require("viewportTop:rect.top" in anchor,'clicked customer viewport position must be stored')
require("fingerprint:rowFingerprint(row)" in anchor,'clicked customer row identity must be stored')
require("anchor.clientId=String(vm.selectedClientId)" in anchor,'selected customer id must be captured after native detail selection')
require("const delta=rect.top-anchor.viewportTop;" in anchor,'return must calculate row displacement from original viewport position')
require("writeTargetScrollTop(target,readTargetScrollTop(target)+delta)" in anchor,'return must correct the real scroll container by row-anchor delta')
require("if(vm.currentPage!=='client-detail'||!anchor)return;" in anchor,'detail back restoration must only run for a captured client anchor')
require("button.querySelector('i.fa-arrow-left')" in anchor,'detail back button must trigger anchor restoration')
require("vm.$nextTick(afterRender)" in anchor,'anchor correction must wait for Vue list render')

for marker in (
    'client-view-transition-v20-soft-detail-entry','growthops-client-view-transition-style','growthops-client-nav-exit',
    'growthops-client-nav-enter','growthops-client-nav-enter-active','resolveSurface','armExit','playEnter','scheduleEnter',
    'prefers-reduced-motion: reduce','cubic-bezier(.16,1,.3,1)','__GROWTHOPS_CLIENT_VIEW_TRANSITION__'
):
    require(marker in transition,f'client view transition marker missing: {marker}')
require("window.addEventListener('pointerdown',event=>" in transition,'detail transition must begin on pointerdown for a responsive exit')
require("if(vm.currentPage!=='clients')return;" in transition,'detail transition must only arm from the client list')
require("const originalOpenClientDetail=vm.openClientDetail;" in transition,'detail transition must wrap the already-isolated native navigation')
require("const fromClients=vm.currentPage==='clients';" in transition,'detail transition must be forward-only from client list')
require("Date.now()-lastActivationAt<1000" in transition,'programmatic detail opens must not be delayed or animated accidentally')
require("result=originalOpenClientDetail.apply(this,args)" in transition,'detail business logic must remain synchronous and authoritative')
require("scheduleEnter();" in transition,'detail content must animate in after Vue renders')
require("vm.$nextTick(run)" in transition,'detail enter animation must wait for Vue render')
require("if(vm.currentPage!=='client-detail')" in transition,'enter animation must abort if navigation did not reach detail')
require("button.querySelector('i.fa-arrow-left')" not in transition,'transition bridge must not interfere with the working detail-back anchor behavior')

require("finalizeClientListNavigation=()=>navigateWithPageScroll('clients')" in bridge,'client save must return using client-list scroll memory')
require("navigateWithPageScroll(vm.form?.id?'client-detail':'clients',button)" in bridge,'client form back must restore destination scroll state')
require("vm.persist=()=>{persistRequested=true;return true}" in bridge,'client save must suppress delayed duplicate persist')
require("const originalNavigate=vm.navigateTo;" in bridge and "vm.navigateTo=()=>true;" in bridge and "vm.navigateTo=originalNavigate" in bridge,'client save navigation suppression must remain intact')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in bridge,'client save must continue cloud sync asynchronously')
require('window.location.replace' not in bridge and 'window.location.reload' not in bridge,'client navigation must not hard refresh')
require('resetScrollNow' not in bridge,'legacy global scroll reset must remain removed')
require("getAttribute('@submit.prevent')" not in bridge,'runtime bridge must not depend on Vue directive attributes after mount')

print('UI_ACTION_OUTPUT_TESTS_OK: index='+hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()+'; bridge='+hashlib.sha256((dist/'cloud-ui-action-bridge.js').read_bytes()).hexdigest()+'; anchor='+hashlib.sha256((dist/'client-scroll-anchor-bridge.js').read_bytes()).hexdigest()+'; transition='+hashlib.sha256((dist/'client-view-transition-bridge.js').read_bytes()).hexdigest())