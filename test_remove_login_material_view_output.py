from pathlib import Path
import hashlib
import re

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

require('平台资产与账号' in html,'platform asset section must remain')
require('growthops-secure-credential-button' not in html,'secure credential view button must be removed from final HTML')
buttons=re.findall(r'<button\b[^>]*>.*?</button>',html,flags=re.S|re.I)
require(not any(('查看登录资料' in button or '隐藏登录资料' in button) for button in buttons),
        'view/hide login material button must not remain in final HTML')
require('登录凭证仅管理员 / 运营可见' not in html,'credential-view fallback control must be removed with the feature')
require('crm_client_account_safe_summary' in security,'safe account summary must remain available')
require("row.passwordCell.textContent=recorded?'••••••••':'未录入'" in security,'masked credential status must remain')
require('管理员点“查看登录资料”后可用眼睛短暂显示' not in security,'removed feature hint must not remain')

print('REMOVE_LOGIN_MATERIAL_VIEW_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest()+'; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
