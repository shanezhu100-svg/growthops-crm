from pathlib import Path
import hashlib
root=Path(__file__).resolve().parent
dist=root/'dist'
html=(dist/'index.html').read_text(encoding='utf-8')
bridge=(dist/'cloud-ui-action-bridge.js').read_text(encoding='utf-8')

def require(c,m):
    if not c: raise SystemExit(m)
security='<script src="/cloud-security-hotfix.js"></script>'
tag='<script src="/cloud-ui-action-bridge.js"></script>'
require(html.count(tag)==1,'UI action bridge tag missing or duplicated')
require(security+tag in html,'UI action bridge must load immediately after security hotfix')
for marker in ('growthops-session-restore-style','growthops-session-restore-guard','growthops-session-restoring','正在恢复登录会话','growthops_crm_token_v2'):
    require(marker in html,f'session restore guard missing: {marker}')
for marker in ('saveOpeningDeal','saveOpeningProvider','saveAdDataRecord','showOpeningModal','showProviderModal','showAdDataModal','client-form-back','client-form-save','client-detail-back','saveClient','stopImmediatePropagation','modalByButton','native-action-bridge-v17-route-scroll-isolation','reportValidity','validateButtonForm','finalizeClientListNavigation','PAGE_SCROLL_PAGES','pageScrollPositions','readScrollTop','writeScrollTop','rememberPageScroll','getPageScroll','restorePageScrollInstant','navigateWithPageScroll','observePageScroll','routeSwitching','scrollingElement','clients','client-form','client-detail','isClientDetailOpenButton','pointerdown','saveNow','window.history.replaceState','clearSessionRestoreCover','pendingClientCloudSaves','trackClientCloudSave','beforeunload','正在同步云端','已同步云端','originalNavigate','previousPage','scrollRestoration'):
    require(marker in bridge,f'UI action bridge marker missing: {marker}')
require("label==='取消'||button.title==='关闭'" in bridge,'modal cancel/close bridge missing')
require("label==='保存客户开户渠道'" in bridge,'opening save bridge missing')
require("label==='保存开户商'" in bridge,'provider save bridge missing')
require("label.includes('更新并同步数据')" in bridge,'ad data update bridge missing')
require("label==='保存修改'||label==='确认合作并创建客户'" in bridge,'client form save button bridge missing')
require("typeof vm.saveClient!=='function'" in bridge,'client save method guard missing')
require("new Set(['clients','client-form','client-detail'])" in bridge,'client views must have independent scroll-memory scope')
require("pageScrollPositions[page]=readScrollTop();" in bridge,'active page scroll position must be remembered independently')
require("const targetTop=getPageScroll(page);" in bridge,'destination page must restore its own saved scroll position')
require("if(sourcePage)rememberPageScroll(sourcePage);" in bridge,'source page scroll must be captured before switching views')
require("finalizeClientListNavigation=()=>navigateWithPageScroll('clients')" in bridge,'client save must return using client-list scroll memory')
require("navigateWithPageScroll(vm.form?.id?'client-detail':'clients')" in bridge,'client cancel/back must restore destination scroll memory')
require("bind(button,'client-detail-back',()=>navigateWithPageScroll('clients'))" in bridge,'client detail back must restore client-list scroll memory')
require("if(vm.currentPage!=='clients')return;" in bridge,'detail entry scroll capture must only run from client management')
require("rememberPageScroll('clients');" in bridge,'client management scroll must be captured immediately before opening detail')
require("pageScrollPositions['client-detail']=0;" in bridge,'new client detail view must start from its own top position')
require("label==='详情'||label==='查看客户详情'" in bridge,'detail buttons must be recognized for scroll capture')
require("button===row.querySelector('td:first-child button')" in bridge,'client-name detail entry must be recognized for scroll capture')
require("window.history.scrollRestoration='manual'" in bridge,'browser scroll restoration must not compete with SPA client-view restoration')
require("root.style.scrollBehavior='auto'" in bridge,'client navigation must disable smooth scroll during view switch')
nav_block=bridge.split('const navigateWithPageScroll=page=>',1)[1].split('const finalizeClientListNavigation',1)[0]
require(nav_block.index('vm.currentPage=page;') < nav_block.index('writeScrollTop(targetTop);'),'destination page must be selected before destination scroll is applied')
require("writeScrollTop(targetTop);" in nav_block,'destination page scroll restore missing')
require("routeSwitching=true;" in nav_block and "routeSwitching=false;" in nav_block,'scroll events must be isolated while switching client views')
require("window.addEventListener('scroll',()=>rememberPageScroll(vm.currentPage),{passive:true})" in bridge,'client scroll memory listener missing')
require("const previousPage=lastObservedPage;" in bridge,'page observer must retain the source page before target restoration')
require("if(page==='client-form'&&previousPage!=='client-form')pageScrollPositions['client-form']=0;" in bridge,'new client edit view must get its own scroll context')
require("if(page==='client-detail'&&previousPage==='clients')pageScrollPositions['client-detail']=0;" in bridge,'client detail must reset its own scroll context when opened from the client list')
observe_block=bridge.split('const observePageScroll=()=>',1)[1].split("window.addEventListener('scroll'",1)[0]
require("if(page===lastObservedPage){\n      rememberPageScroll(page);\n      return;\n    }" in observe_block,'same-page observation must be the only observer path that records current physical scroll')
require("if(routeSwitching)return;" in observe_block,'observer must not interfere with an explicit route restoration')
require("restorePageScrollInstant(page);" in observe_block,'native client-view changes must restore the destination page before scroll capture resumes')
changed_path=observe_block.split('const previousPage=lastObservedPage;',1)[1]
require('rememberPageScroll(page);' not in changed_path,'page-change observer must not write inherited source scroll into the destination page')
restore_block=bridge.split('const restorePageScrollInstant=page=>',1)[1].split('const navigateWithPageScroll=page=>',1)[0]
require("const targetTop=getPageScroll(page);" in restore_block,'native route restore must freeze the destination top before rendering settles')
require("routeSwitching=true;" in restore_block and "routeSwitching=false;" in restore_block,'native route restore must suppress scroll-memory writes while applying the target position')
require("vm.$nextTick(settle)" in restore_block,'native route restore must wait for Vue DOM rendering')
require("setTimeout(finish,80)" in restore_block,'native route restore must retry after layout settles')
require('resetScrollNow' not in bridge,'legacy global scroll-to-top navigation must be removed')
require('SAVE_TRANSITION_MS' not in bridge and 'SAVE_TRANSITION_ID' not in bridge,'fixed save-transition delay/cover must be removed')
require('showClientSaveTransition' not in bridge and 'hideClientSaveTransition' not in bridge,'legacy client save masking must be removed')
require('正在保存客户…' not in bridge,'old save transition screen must not remain')
require("vm.formDirty!==false||!vm.selectedClientId" in bridge,'client save success guard missing')
require("vm.persist=()=>{persistRequested=true;return true}" in bridge,'client save must suppress delayed duplicate persist before queued cloud commit')
require("const originalNavigate=vm.navigateTo;" in bridge,'client save must capture legacy internal navigation')
require("vm.navigateTo=()=>true;" in bridge,'client save must suppress legacy internal navigation before final return')
require("vm.navigateTo=originalNavigate" in bridge,'client save must restore original navigation immediately after business mutation')
client_block=bridge.split("if(label==='保存修改'||label==='确认合作并创建客户')",1)[1].split('    });\n      });',1)[0]
require('finalizeClientListNavigation();' in client_block,'client save must return immediately to remembered client-list position')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in client_block,'client save must continue cloud sync asynchronously')
require('await cloud.saveNow()' not in client_block,'client save must not block UI on cloud RPC')
require(client_block.index('finalizeClientListNavigation();') < client_block.index('trackClientCloudSave(cloud.saveNow())'),'client list return must not wait for cloud sync startup')
require('SAVE_TRANSITION' not in client_block and 'setTimeout(()=>{' not in client_block,'client save must not pause on the edit form before returning')
require("window.addEventListener('beforeunload',protectPendingSave)" in bridge,'pending cloud save unload protection missing')
require("window.removeEventListener('beforeunload',protectPendingSave)" in bridge,'pending cloud save unload protection cleanup missing')
require('window.location.replace' not in bridge,'client save must not hard-refresh the page')
require('window.location.reload' not in bridge,'client save must not reload the page')
require('hardClientReturn' not in bridge,'legacy hard-refresh client return must be removed')
require('RETURN_QUERY' not in bridge and 'RETURN_CLIENT_KEY' not in bridge,'legacy refresh return markers must be removed')
require("getAttribute('@submit.prevent')" not in bridge,'runtime bridge must not depend on Vue directive attributes after mount')
print('UI_ACTION_OUTPUT_TESTS_OK: index='+hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()+'; bridge='+hashlib.sha256((dist/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
