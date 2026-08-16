from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
security_path = root / 'dist' / 'cloud-security-hotfix.js'
security = security_path.read_text(encoding='utf-8')

def require(condition, message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'findRevealHost',
    "vm.currentPage!=='client-detail'",
    "String(node.textContent||'').trim()==='平台资产与账号'",
    "vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null",
    "host.header.appendChild(button)",
    "host.titleBlock.style.marginRight='auto'",
    'ADMIN 按需从 Vault 临时读取敏感凭证，60 秒后自动清除',
    '安全查看客户凭证',
    'crm_reveal_client_secrets',
    'setTimeout(clearReveal,60000)',
):
    require(marker in security, f'secure reveal in-page marker missing: {marker}')

require('position:fixed;right:18px;bottom:72px' not in security, 'secure reveal must not be a floating fixed button')
require('z-index:2147482500' not in security, 'legacy floating reveal z-index remains')
ensure_block = security.split('function ensureRevealButton(){',1)[1].split("document.addEventListener('visibilitychange'",1)[0]
require('document.body.appendChild(button)' not in ensure_block, 'secure reveal button must not fall back to document body')
require("if(!visible){" in ensure_block and "if(button)button.remove();" in ensure_block, 'secure reveal must be removed outside ADMIN client detail')
require("if(document.getElementById(MODAL_ID))clearReveal();" in ensure_block, 'open credential reveal must close when leaving its authorized detail context')
require('navigator.clipboard' not in security, 'secure reveal must not auto-copy credentials')
require('console.log' not in security and 'console.error' not in security, 'secure reveal must not log secret-bearing objects')

print('SECURITY_REVEAL_UI_OUTPUT_TESTS_OK: security=' + hashlib.sha256(security_path.read_bytes()).hexdigest())
