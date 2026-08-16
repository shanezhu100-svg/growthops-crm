from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

old_header='''<div class="p-5 border-b border-slate-100 flex items-center justify-between"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div><button v-if="canViewCredentials()" @click="credentialsVisible=!credentialsVisible" class="text-xs font-semibold text-indigo-600"><i :class="credentialsVisible?'fa-regular fa-eye-slash':'fa-regular fa-eye'" class="mr-1"></i>{{ credentialsVisible?'隐藏登录资料':'查看登录资料' }}</button><span v-else class="text-[10px] font-bold text-slate-400"><i class="fa-solid fa-lock mr-1"></i>登录凭证仅管理员 / 运营可见</span></div>'''
new_header='''<div class="p-5 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap"><div><h3 class="font-extrabold text-sm">平台资产与账号</h3><p class="text-[11px] text-slate-400 mt-1">BM / BC / 广告账号 / 登录资料集中归档；费用数据在投放分析维护</p></div><div class="flex items-center gap-2 flex-wrap justify-end"><button v-if="currentUser?.role==='ADMIN'" id="growthops-secure-credential-button" type="button" title="从 Vault 临时读取登录资料并原位显示，60 秒后自动清除" class="text-xs font-semibold text-indigo-600"><i class="fa-regular fa-eye mr-1"></i>查看登录资料</button><button v-else-if="canViewCredentials()" @click="credentialsVisible=!credentialsVisible" class="text-xs font-semibold text-indigo-600"><i :class="credentialsVisible?'fa-regular fa-eye-slash':'fa-regular fa-eye'" class="mr-1"></i>{{ credentialsVisible?'隐藏登录资料':'查看登录资料' }}</button><span v-else class="text-[10px] font-bold text-slate-400"><i class="fa-solid fa-lock mr-1"></i>登录凭证仅管理员 / 运营可见</span></div></div>'''
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
      if(revealData)clearReveal();
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

const_marker="  const MODAL_ID='growthops-secure-credential-modal';\n"
if security.count(const_marker)!=1:
    raise SystemExit(f'Unexpected secure reveal constant count: {security.count(const_marker)}')
security=security.replace(const_marker,const_marker+"  const INLINE_ATTR='data-growthops-vault-inline';\n",1)

clear_start=security.find('  function clearReveal(){')
clear_end=security.find('  function make(',clear_start)
if clear_start<0 or clear_end<0:
    raise SystemExit('Unable to locate secure reveal cleanup block')
new_clear='''  function setRevealButtonState(visible){
    const button=document.getElementById(BUTTON_ID);
    if(!button)return;
    button.innerHTML=visible?'<i class="fa-regular fa-eye-slash mr-1"></i>隐藏登录资料':'<i class="fa-regular fa-eye mr-1"></i>查看登录资料';
    button.title=visible?'隐藏当前临时显示的 Vault 登录资料':'从 Vault 临时读取登录资料并原位显示，60 秒后自动清除';
  }

  function clearReveal(){
    clearTimeout(revealTimer);
    revealTimer=null;
    revealData=null;
    document.querySelectorAll(`[${INLINE_ATTR}="1"]`).forEach(el=>{
      if(el.dataset.growthopsVaultPrevious!==undefined)el.textContent=el.dataset.growthopsVaultPrevious;
      delete el.dataset.growthopsVaultPrevious;
      el.removeAttribute(INLINE_ATTR);
      el.removeAttribute('data-growthops-vault-kind');
      el.removeAttribute('title');
    });
    const modal=document.getElementById(MODAL_ID);
    if(modal)modal.remove();
    setRevealButtonState(false);
  }

'''
security=security[:clear_start]+new_clear+security[clear_end:]

render_start=security.find('  function renderRevealModal(clientId,secretTree){')
render_end=security.find('  async function revealSelectedClient(){',render_start)
if render_start<0 or render_end<0:
    raise SystemExit('Unable to locate secure reveal render block')
new_render='''  const normalizedFieldLabel=field=>String(field?.label||'').toLowerCase().replace(/[^a-z0-9#]+/g,'');
  const platformForCard=card=>{
    const value=String(card?.textContent||'').toLowerCase();
    if(value.includes('facebook'))return 'facebook';
    if(value.includes('tiktok'))return 'tiktok';
    return '';
  };
  const cardIdentityTokens=card=>{
    const value=String(card?.textContent||'');
    return [...new Set((value.match(/[A-Za-z0-9_-]{6,}/g)||[]).map(v=>v.toLowerCase()))];
  };
  const secretKindScore=(key,kind)=>{
    if(kind==='account')return key.includes('loginaccount')?30:0;
    if(kind==='password'){
      if(key.includes('loginpassword'))return 34;
      if(key.endsWith('password')||key.includes('passwd')||key.endsWith('pwd'))return 22;
      return 0;
    }
    if(kind==='twofa'){
      if(key.includes('twofactor')||key.includes('2fa')||key.includes('totp'))return 34;
      if(key.includes('secretkey'))return 20;
      return 0;
    }
    return 0;
  };
  const scoreSecretField=(field,platform,kind,card)=>{
    const key=normalizedFieldLabel(field);
    let score=secretKindScore(key,kind);
    if(!score)return 0;
    if(platform==='facebook'){
      if(key.includes('fblogin'))score+=45;
      if(key.includes('facebook')||key.includes('fbaccount')||key.includes('fbaccounts'))score+=24;
      if(key.includes('tklogin')||key.includes('tiktok'))score-=70;
    }else if(platform==='tiktok'){
      if(key.includes('tklogin'))score+=45;
      if(key.includes('tiktok')||key.includes('tkaccount')||key.includes('tkaccounts'))score+=24;
      if(key.includes('fblogin')||key.includes('facebook'))score-=70;
    }
    for(const token of cardIdentityTokens(card))if(key.includes(token))score+=55;
    return score;
  };
  const bestSecretValue=(fields,platform,kind,card)=>{
    let best=null,bestScore=0;
    for(const field of fields){
      const score=scoreSecretField(field,platform,kind,card);
      if(score>bestScore){best=field;bestScore=score}
    }
    return bestScore>0?String(best?.value||''):'';
  };
  const exactLeaf=(root,label)=>[...root.querySelectorAll('*')].find(el=>el.children.length===0&&String(el.textContent||'').replace(/\\s+/g,' ').trim()===label)||null;
  const credentialCardForLabel=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i++,node=node.parentElement){
      const value=String(node.textContent||'');
      const hasPlatform=value.includes('Facebook')||value.includes('TikTok');
      if(hasPlatform&&value.includes('登录账号')&&value.includes('密码 / 2FA'))return node;
    }
    return null;
  };
  const valueCellForLabel=label=>{
    const row=label?.parentElement;
    if(!row)return null;
    const children=[...row.children].filter(el=>el!==label);
    return children.length?children[children.length-1]:null;
  };
  const locateCredentialRows=()=>{
    const rows=[];
    const labels=[...document.querySelectorAll('*')].filter(el=>el.children.length===0&&['登录账号','密码 / 2FA'].includes(String(el.textContent||'').replace(/\\s+/g,' ').trim()));
    const seen=new Set();
    for(const label of labels){
      const card=credentialCardForLabel(label);
      if(!card||seen.has(card))continue;
      seen.add(card);
      const accountLabel=exactLeaf(card,'登录账号');
      const passwordLabel=exactLeaf(card,'密码 / 2FA');
      rows.push({card,platform:platformForCard(card),accountCell:valueCellForLabel(accountLabel),passwordCell:valueCellForLabel(passwordLabel)});
    }
    return rows.filter(row=>row.platform&&(row.accountCell||row.passwordCell));
  };
  const setInlineValue=(cell,value,kind)=>{
    if(!cell||!value)return false;
    if(cell.getAttribute(INLINE_ATTR)!=='1')cell.dataset.growthopsVaultPrevious=cell.textContent||'';
    cell.textContent=value;
    cell.setAttribute(INLINE_ATTR,'1');
    cell.setAttribute('data-growthops-vault-kind',kind);
    cell.title='Vault 临时显示 · 60 秒后自动隐藏';
    return true;
  };
  function applyInlineSecrets(secretTree){
    const fields=flattenSecretFields(secretTree);
    let applied=0;
    for(const row of locateCredentialRows()){
      const account=bestSecretValue(fields,row.platform,'account',row.card);
      const password=bestSecretValue(fields,row.platform,'password',row.card);
      const twofa=bestSecretValue(fields,row.platform,'twofa',row.card);
      if(setInlineValue(row.accountCell,account,'account'))applied+=1;
      const secureParts=[];
      if(password)secureParts.push(password);
      if(twofa)secureParts.push(`2FA: ${twofa}`);
      if(setInlineValue(row.passwordCell,secureParts.join('  ·  '),'password-2fa'))applied+=1;
    }
    return applied;
  }
  function renderRevealModal(clientId,secretTree){
    clearReveal();
    revealData=secretTree;
    const applied=applyInlineSecrets(secretTree);
    if(!applied){
      revealData=null;
      vm.notify('该客户当前没有可在账号卡片中显示的登录账号、密码或 2FA');
      return;
    }
    setRevealButtonState(true);
    revealTimer=setTimeout(clearReveal,60000);
  }

'''
security=security[:render_start]+new_render+security[render_end:]

toggle_marker="  async function revealSelectedClient(){\n    if(vm.currentUser?.role!=='ADMIN'){"
if security.count(toggle_marker)!=1:
    raise SystemExit(f'Unexpected reveal handler count: {security.count(toggle_marker)}')
security=security.replace(toggle_marker,"  async function revealSelectedClient(){\n    if(vm.currentUser?.role!=='ADMIN'){",1)
insert_after="      return;\n    }\n    const clientId=vm.selectedClientId;"
if security.count(insert_after)!=1:
    raise SystemExit(f'Unexpected reveal authorization block count: {security.count(insert_after)}')
security=security.replace(insert_after,"      return;\n    }\n    if(revealData){clearReveal();return;}\n    const clientId=vm.selectedClientId;",1)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print('SECURITY_REVEAL_UI_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
