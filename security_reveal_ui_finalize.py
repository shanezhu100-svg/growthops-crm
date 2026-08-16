from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

old_header='''<div class="p-5 border-b border-slate-100 flex items-center justify-between"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div><button v-if="canViewCredentials()" @click="credentialsVisible=!credentialsVisible" class="text-xs font-semibold text-indigo-600"><i :class="credentialsVisible?'fa-regular fa-eye-slash':'fa-regular fa-eye'" class="mr-1"></i>{{ credentialsVisible?'隐藏登录资料':'查看登录资料' }}</button><span v-else class="text-[10px] font-bold text-slate-400"><i class="fa-solid fa-lock mr-1"></i>登录凭证仅管理员 / 运营可见</span></div>'''
new_header='''<div class="p-5 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div><div class="flex items-center gap-2 flex-wrap justify-end"><button v-if="currentUser?.role==='ADMIN'" id="growthops-secure-credential-button" type="button" title="从 Vault 临时读取登录资料，60 秒后自动清除" class="text-xs font-semibold text-indigo-600"><i class="fa-regular fa-eye mr-1"></i>查看登录资料</button><button v-else-if="canViewCredentials()" @click="credentialsVisible=!credentialsVisible" class="text-xs font-semibold text-indigo-600"><i :class="credentialsVisible?'fa-regular fa-eye-slash':'fa-regular fa-eye'" class="mr-1"></i>{{ credentialsVisible?'隐藏登录资料':'查看登录资料' }}</button><span v-else class="text-[10px] font-bold text-slate-400"><i class="fa-solid fa-lock mr-1"></i>登录凭证仅管理员 / 运营可见</span></div></div>'''
if html.count(old_header)!=1:
    raise SystemExit(f'Unexpected client detail asset header count: {html.count(old_header)}')
html=html.replace(old_header,new_header,1)

old_button='''  function ensureRevealButton(){
    let button=document.getElementById(BUTTON_ID);
    if(!button){
      button=make('button',{
        id:BUTTON_ID,
        type:'button',
        style:'position:fixed;right:18px;bottom:72px;z-index:2147482500;border:0;border-radius:999px;background:#0f172a;color:#fff;padding:10px 14px;box-shadow:0 10px 30px rgba(15,23,42,.2);font:700 13px/1.2 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;cursor:pointer;'
      },'安全查看客户凭证');
      button.addEventListener('click',revealSelectedClient);
      document.body.appendChild(button);
    }

    const visible=vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null;
    button.style.display=visible?'block':'none';
  }
'''
new_button='''  function ensureRevealButton(){
    const visible=vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null;
    const button=document.getElementById(BUTTON_ID);
    if(!visible){
      if(document.getElementById(MODAL_ID))clearReveal();
      return;
    }
    if(!button)return;
    if(!button.__growthOpsRevealBound){
      button.addEventListener('click',revealSelectedClient);
      button.__growthOpsRevealBound=true;
    }
  }
'''
if security.count(old_button)!=1:
    raise SystemExit(f'Unexpected floating reveal button block count: {security.count(old_button)}')
security=security.replace(old_button,new_button,1)

old_modal_title="'客户敏感凭证 · 临时查看'"
new_modal_title="'登录资料 · 安全查看'"
if security.count(old_modal_title)!=1:
    raise SystemExit(f'Unexpected secure reveal modal title count: {security.count(old_modal_title)}')
security=security.replace(old_modal_title,new_modal_title,1)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print('SECURITY_REVEAL_UI_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
