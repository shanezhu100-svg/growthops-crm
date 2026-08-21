from pathlib import Path
import hashlib
import re

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

old_header='''<div class="p-5 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div><div class="flex items-center gap-2 flex-wrap justify-end"><button v-if="currentUser?.role==='ADMIN'" id="growthops-secure-credential-button" type="button" title="从 Vault 临时读取登录资料，密码 / 2FA 需单独显示，30 秒后自动清除" class="text-xs font-semibold text-indigo-600"><i class="fa-regular fa-eye mr-1"></i>查看登录资料</button><button v-else-if="canViewCredentials()" @click="credentialsVisible=!credentialsVisible" class="text-xs font-semibold text-indigo-600"><i :class="credentialsVisible?'fa-regular fa-eye-slash':'fa-regular fa-eye'" class="mr-1"></i>{{ credentialsVisible?'隐藏登录资料':'查看登录资料' }}</button><span v-else class="text-[10px] font-bold text-slate-400"><i class="fa-solid fa-lock mr-1"></i>登录凭证仅管理员 / 运营可见</span></div></div>'''
new_header='''<div class="p-5 border-b border-slate-100"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div></div>'''
if html.count(old_header)!=1:
    raise SystemExit(f'Unexpected platform asset credential header count: {html.count(old_header)}')
html=html.replace(old_header,new_header,1)

# Defense in depth: remove any other rendered button carrying the same view/hide action.
button_pattern=re.compile(r'<button\b[^>]*>.*?</button>',re.S|re.I)
removed=[]
def drop_login_material_button(match):
    block=match.group(0)
    if '查看登录资料' in block or '隐藏登录资料' in block:
        removed.append(block)
        return ''
    return block
html=button_pattern.sub(drop_login_material_button,html)

old_hint='密码 / 2FA 已安全保存在 Vault；管理员点“查看登录资料”后可用眼睛短暂显示'
if security.count(old_hint)!=1:
    raise SystemExit(f'Unexpected credential reveal hint count: {security.count(old_hint)}')
security=security.replace(old_hint,'密码 / 2FA 已安全保存在 Vault',1)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print('REMOVE_LOGIN_MATERIAL_VIEW_FINALIZE_OK: extra_buttons_removed='+str(len(removed))+'; index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
