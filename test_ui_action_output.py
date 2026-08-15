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
for marker in ('saveOpeningDeal','saveOpeningProvider','saveAdDataRecord','showOpeningModal','showProviderModal','showAdDataModal','client-form-back','stopImmediatePropagation','modalByButton','native-action-bridge-v2'):
    require(marker in bridge,f'UI action bridge marker missing: {marker}')
require("label==='取消'||button.title==='关闭'" in bridge,'modal cancel/close bridge missing')
require("label==='保存客户开户渠道'" in bridge,'opening save bridge missing')
require("label==='保存开户商'" in bridge,'provider save bridge missing')
require("label.includes('更新并同步数据')" in bridge,'ad data update bridge missing')
require("getAttribute('@submit.prevent')" not in bridge,'runtime bridge must not depend on Vue directive attributes after mount')
print('UI_ACTION_OUTPUT_TESTS_OK: index='+hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()+'; bridge='+hashlib.sha256((dist/'cloud-ui-action-bridge.js').read_bytes()).hexdigest())
