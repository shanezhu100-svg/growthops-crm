from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    '平台资产与账号',
    'id="growthops-secure-credential-button"',
    "v-if=\"currentUser?.role==='ADMIN'\"",
    'v-else-if="canViewCredentials()"',
    '从 Vault 临时读取登录资料，60 秒后自动清除',
    '查看登录资料',
):
    require(marker in html,f'unified login credential control missing: {marker}')

require(html.count('id="growthops-secure-credential-button"')==1,'secure login reveal button must exist exactly once in Vue template')
require('安全查看客户凭证' not in html,'separate secure credential button must be removed from client detail header')
require('@click="credentialsVisible=!credentialsVisible"' in html,'non-ADMIN credential visibility behavior must remain available to existing permitted roles')
require('登录资料 · 安全查看' in security,'secure reveal modal must use the unified login-details wording')
require('position:fixed;right:18px;bottom:72px' not in security,'legacy floating reveal button remains')
require('document.body.appendChild(button)' not in security,'security script must not append reveal control into Vue-owned DOM')
require('button.remove()' not in security,'security script must not remove Vue-owned reveal control')
require('host.header.appendChild(button)' not in security,'security script must not mutate client-detail child structure')
require("const button=document.getElementById(BUTTON_ID);" in security,'security script must locate the Vue-owned reveal control')
require("button.addEventListener('click',revealSelectedClient);" in security,'secure reveal click handler missing')
require('button.__growthOpsRevealBound=true;' in security,'secure reveal duplicate-listener guard missing')
require("vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null" in security,'secure reveal context authorization check missing')
require("if(document.getElementById(MODAL_ID))clearReveal();" in security,'reveal modal must close outside authorized detail context')
require("crm_reveal_client_secrets" in security,'Vault reveal RPC missing')
require('setTimeout(clearReveal,60000)' in security,'60-second reveal auto-clear missing')
require('navigator.clipboard' not in security,'secure reveal must not auto-copy credentials')

print('SECURITY_REVEAL_UI_OUTPUT_TESTS_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
