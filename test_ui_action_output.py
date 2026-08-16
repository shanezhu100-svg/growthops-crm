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
for marker in ('saveOpeningDeal','saveOpeningProvider','saveAdDataRecord','showOpeningModal','showProviderModal','showAdDataModal','client-form-back','client-form-save','saveClient','stopImmediatePropagation','modalByButton','native-action-bridge-v14-save-transition','reportValidity','validateButtonForm','finalizeClientListNavigation','navigateNoCarry','resetScrollNow','scrollingElement','SAVE_TRANSITION_MS=180','SAVE_TRANSITION_ID','showClientSaveTransition','hideClientSaveTransition','正在保存客户','clients','client-detail','saveNow','window.history.replaceState','clearSessionRestoreCover','pendingClientCloudSaves','trackClientCloudSave','beforeunload','正在同步云端','已同步云端','originalNavigate'):
    require(marker in bridge,f'UI action bridge marker missing: {marker}')
require("label==='取消'||button.title==='关闭'" in bridge,'modal cancel/close bridge missing')
require("label==='保存客户开户渠道'" in bridge,'opening save bridge missing')
require("label==='保存开户商'" in bridge,'provider save bridge missing')
require("label.includes('更新并同步数据')" in bridge,'ad data update bridge missing')
require("label==='保存修改'||label==='确认合作并创建客户'" in bridge,'client form save button bridge missing')
require("typeof vm.saveClient!=='function'" in bridge,'client save method guard missing')
require("finalizeClientListNavigation=()=>navigateNoCarry('clients')" in bridge,'client save must return to client list with isolated scroll')
require("navigateNoCarry(vm.form?.id?'client-detail':'clients')" in bridge,'client cancel/back must use isolated direct navigation')
require("root.style.scrollBehavior='auto'" in bridge,'client navigation must disable smooth scroll during view switch')
require("resetScrollNow();\n    vm.currentPage=page;" in bridge,'scroll position must be reset before destination page is switched')
require("if(vm.currentPage!==page)" in bridge,'destination page must be stabilized after Vue render')
require("requestAnimationFrame(()=>{\n        resetScrollNow();" in bridge,'destination scroll must be rechecked after render')
require("scroller.scrollTop=0" in bridge,'client navigation must reset the shared document scroller')
require("document.documentElement.scrollTop=0" in bridge,'root scroll reset missing')
require("document.body.scrollTop=0" in bridge,'body scroll reset missing')
require("vm.$forceUpdate" in bridge.split('const navigateNoCarry=page=>',1)[1].split('const finalizeClientListNavigation',1)[0],'direct client navigation must force a reliable Vue redraw')
require("vm.formDirty!==false||!vm.selectedClientId" in bridge,'client save success guard missing')
require("vm.persist=()=>{persistRequested=true;return true}" in bridge,'client save must suppress delayed duplicate persist before queued cloud commit')
require("const originalNavigate=vm.navigateTo;" in bridge,'client save must capture legacy internal navigation')
require("vm.navigateTo=()=>true;" in bridge,'client save must suppress legacy internal navigation before final return')
require("vm.navigateTo=originalNavigate" in bridge,'client save must restore original navigation immediately after business mutation')
require("position:fixed;inset:0;z-index:460" in bridge,'client save transition must fully mask the outgoing form')
require("cover.setAttribute('role','status')" in bridge,'client save transition accessibility status missing')
client_block=bridge.split("if(label==='保存修改'||label==='确认合作并创建客户')",1)[1].split('    });\n      });',1)[0]
require('showClientSaveTransition();' in client_block,'client save must mask the old form before returning')
require('finalizeClientListNavigation();' in client_block,'client save must switch to client list immediately under the transition cover')
require('trackClientCloudSave(cloud.saveNow()).catch(()=>{});' in client_block,'client save must continue cloud sync asynchronously')
require('await cloud.saveNow()' not in client_block,'client save must not block UI on cloud RPC')
require('hideClientSaveTransition();' in client_block and 'SAVE_TRANSITION_MS' in client_block,'client save transition must clear after a short fixed interval')
require(client_block.index('showClientSaveTransition();') < client_block.index('finalizeClientListNavigation();'),'outgoing client form must be masked before page switch')
require(client_block.index('finalizeClientListNavigation();') < client_block.index('trackClientCloudSave(cloud.saveNow())'),'client list switch must not wait for cloud sync startup')
require("window.addEventListener('beforeunload',protectPendingSave)" in bridge,'pending cloud save unload protection missing')
require("window.removeEventListener('beforeunload',protectPendingSave)" in bridge,'pending cloud save unload protection cleanup missing')
require('window.location.replace' not in bridge,'client save must not hard-refresh the page')
require('window.location.reload' not in bridge,'client save must not reload the page')
require('hardClientReturn' not in bridge,'legacy hard-refresh client return must be removed')
require('RETURN_QUERY' not in bridge and 'RETURN_CLIENT_KEY' not in bridge,'legacy refresh return markers must be removed')
require("getAttribute('@submit.prevent')" not in bridge,'runtime bridge must not depend on Vue directive attributes after mount')
print('UI_ACTION_OUTPUT_TESTS_OK: index='+hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()+'; bridge='+hashlib.sha256((dist/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
