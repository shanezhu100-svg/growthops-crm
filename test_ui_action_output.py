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
for marker in ('saveOpeningDeal','saveOpeningProvider','saveAdDataRecord','showOpeningModal','showProviderModal','showAdDataModal','client-form-back','client-form-save','saveClient','stopImmediatePropagation','modalByButton','native-action-bridge-v7','reportValidity','validateButtonForm','finalizeClientListNavigation','clients','saveNow','window.history.replaceState','clearSessionRestoreCover'):
    require(marker in bridge,f'UI action bridge marker missing: {marker}')
require("label==='取消'||button.title==='关闭'" in bridge,'modal cancel/close bridge missing')
require("label==='保存客户开户渠道'" in bridge,'opening save bridge missing')
require("label==='保存开户商'" in bridge,'provider save bridge missing')
require("label.includes('更新并同步数据')" in bridge,'ad data update bridge missing')
require("label==='保存修改'||label==='确认合作并创建客户'" in bridge,'client form save button bridge missing')
require("typeof vm.saveClient!=='function'" in bridge,'client save method guard missing')
require("vm.currentPage='clients'" in bridge,'client save must return to client list')
require("vm.navigateTo?.('clients')" in bridge,'client save must use SPA client-list navigation')
require("vm.formDirty!==false||!vm.selectedClientId" in bridge,'client save success guard missing')
require("vm.persist=()=>{persistRequested=true;return true}" in bridge,'client save must suppress delayed duplicate persist before queued cloud commit')
require("await cloud.saveNow()" in bridge,'client save must await serialized cloud commit')
require('window.location.replace' not in bridge,'client save must not hard-refresh the page')
require('window.location.reload' not in bridge,'client save must not reload the page')
require('hardClientReturn' not in bridge,'legacy hard-refresh client return must be removed')
require('RETURN_QUERY' not in bridge and 'RETURN_CLIENT_KEY' not in bridge,'legacy refresh return markers must be removed')
require("getAttribute('@submit.prevent')" not in bridge,'runtime bridge must not depend on Vue directive attributes after mount')
print('UI_ACTION_OUTPUT_TESTS_OK: index='+hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()+'; bridge='+hashlib.sha256((dist/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
