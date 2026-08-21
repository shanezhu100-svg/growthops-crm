from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

# Google / Instagram credential cells must never read login/password values directly
# from the ordinary Vue state. The safe summary RPC owns login identifiers + password
# presence; the full Vault reveal RPC owns actual password / 2FA values.
start=html.find('Google 资产')
instagram=html.find('Instagram 资产',start+1)
end=html.find('<div class="flex justify-end">',instagram+1)
if min(start,instagram,end)<0:
    raise SystemExit('Unable to bound Google/Instagram asset region')
region=html[start:end]

login_expr="{{ credentialsVisible ? (account.loginAccount || '未录入') : (account.loginAccount ? maskAccount(account.loginAccount) : '未录入') }}"
password_expr="{{ credentialsVisible ? (account.loginPassword || '未录入') : (account.loginPassword ? '••••••••••••' : '未录入') }}"
if region.count(login_expr)!=2:
    raise SystemExit(f'Expected two Google/Instagram login expressions, got {region.count(login_expr)}')
if region.count(password_expr)!=2:
    raise SystemExit(f'Expected two Google/Instagram password expressions, got {region.count(password_expr)}')
region=region.replace(login_expr,'读取中…',2)
region=region.replace(password_expr,'读取中…',2)
html=html[:start]+region+html[end:]

const_marker="  const STATUS_ATTR='data-growthops-credential-status';\n"
if security.count(const_marker)!=1:
    raise SystemExit(f'Unexpected STATUS_ATTR marker count: {security.count(const_marker)}')
security=security.replace(const_marker,const_marker+"  const LOGIN_IDENTIFIER_ATTR='data-growthops-login-identifier';\n",1)

state_marker="  let credentialStatusFetchedAt=0;\n"
if security.count(state_marker)!=1:
    raise SystemExit(f'Unexpected credential status state marker count: {security.count(state_marker)}')
security=security.replace(
    state_marker,
    state_marker+"  let accountSafeSummaryClientId='';\n  let accountSafeSummaryData=null;\n  let accountSafeSummaryPromise=null;\n  let accountSafeSummaryFetchedAt=0;\n",
    1,
)

# Expand secure inline reveal row detection from FB/TK to all four account platforms.
seg_start=security.find("  const platformForCard=card=>{")
seg_end=security.find("  const prepareInlineCell=(cell,kind)=>{",seg_start)
if seg_start<0 or seg_end<0:
    raise SystemExit('Unable to locate credential row helper segment')
new_segment=r'''  const platformForCard=card=>{
    const value=String(card?.textContent||'').toLowerCase();
    if(value.includes('facebook'))return 'facebook';
    if(value.includes('tiktok'))return 'tiktok';
    if(value.includes('google'))return 'google';
    if(value.includes('instagram'))return 'instagram';
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
      if(key.includes('tklogin')||key.includes('tiktok')||key.includes('googleaccounts')||key.includes('instagramaccounts'))score-=70;
    }else if(platform==='tiktok'){
      if(key.includes('tklogin'))score+=45;
      if(key.includes('tiktok')||key.includes('tkaccount')||key.includes('tkaccounts'))score+=24;
      if(key.includes('fblogin')||key.includes('facebook')||key.includes('googleaccounts')||key.includes('instagramaccounts'))score-=70;
    }else if(platform==='google'){
      if(key.includes('googleaccounts')||key.includes('googleaccount'))score+=45;
      if(key.includes('facebook')||key.includes('tiktok')||key.includes('instagramaccounts'))score-=70;
    }else if(platform==='instagram'){
      if(key.includes('instagramaccounts')||key.includes('instagramaccount'))score+=45;
      if(key.includes('facebook')||key.includes('tiktok')||key.includes('googleaccounts'))score-=70;
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
  const exactLeaf=(root,label)=>[...root.querySelectorAll('*')].find(el=>el.children.length===0&&String(el.textContent||'').replace(/\s+/g,' ').trim()===label)||null;
  const credentialCardForLabel=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i++,node=node.parentElement){
      const value=String(node.textContent||'');
      if(platformForCard(node)&&value.includes('密码 / 2FA'))return node;
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
    const accountLabels=new Set(['登录账号','登录邮箱','登录邮箱 / 手机号']);
    const labels=[...document.querySelectorAll('*')].filter(el=>el.children.length===0&&(accountLabels.has(cleanText(el))||cleanText(el)==='密码 / 2FA'));
    const seen=new Set();
    for(const label of labels){
      const card=credentialCardForLabel(label);
      if(!card||seen.has(card))continue;
      const platform=platformForCard(card);
      if(!platform)continue;
      seen.add(card);
      const accountLabelText=platform==='google'?'登录邮箱':platform==='instagram'?'登录邮箱 / 手机号':'登录账号';
      const accountLabel=exactLeaf(card,accountLabelText);
      const passwordLabel=exactLeaf(card,'密码 / 2FA');
      rows.push({card,platform,accountCell:valueCellForLabel(accountLabel),passwordCell:valueCellForLabel(passwordLabel)});
    }
    return rows.filter(row=>row.platform&&(row.accountCell||row.passwordCell));
  };
'''
security=security[:seg_start]+new_segment+security[seg_end:]

insert_marker="  const applyCredentialLoadingToCards=()=>{\n"
if security.count(insert_marker)!=1:
    raise SystemExit(f'Unexpected account summary insertion marker count: {security.count(insert_marker)}')
summary_helpers=r'''  const currentExternalAssetAccount=platform=>{
    const client=vm.selectedAssetsClient||{};
    const isGoogle=platform==='google';
    const list=isGoogle?(client.googleAccounts||[]):(client.instagramAccounts||[]);
    const pager=isGoogle?'GOOGLE':'INSTAGRAM';
    if(!Array.isArray(list)||!list.length)return null;
    if(typeof vm.getPagedItem==='function')return vm.getPagedItem(list,'assets',pager)||list[0]||null;
    return list[0]||null;
  };
  const summaryForCredentialRow=row=>{
    if(!accountSafeSummaryData)return null;
    if(row.platform==='facebook'||row.platform==='tiktok')return accountSafeSummaryData?.[row.platform]||null;
    const list=row.platform==='google'?accountSafeSummaryData?.googleAccounts:accountSafeSummaryData?.instagramAccounts;
    if(!Array.isArray(list)||!list.length)return null;
    const current=currentExternalAssetAccount(row.platform);
    const currentId=String(current?.id??'');
    if(currentId){
      const match=list.find(item=>String(item?.id??'')===currentId);
      if(match)return match;
    }
    return list.length===1?list[0]:null;
  };
  const applyAccountSafeSummaryToCards=()=>{
    if(!isAccountAssetPage()||!accountSafeSummaryData)return;
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==accountSafeSummaryClientId)return;
    normalizeOtherAccountAssetTypography();
    for(const row of locateCredentialRows()){
      const summary=summaryForCredentialRow(row)||{};
      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'){
        matchCredentialValueTypography(row.accountCell);
        const login=String(summary.loginAccount||'').trim();
        row.accountCell.textContent=login||'未录入';
        row.accountCell.setAttribute(LOGIN_IDENTIFIER_ATTR,'1');
        row.accountCell.title=login?'登录账号由受控 Vault 摘要接口读取；不包含密码':'Vault 中未检测到登录账号';
      }
      if(row.passwordCell&&row.passwordCell.getAttribute(INLINE_ATTR)!=='1'){
        matchCredentialValueTypography(row.passwordCell);
        const recorded=Boolean(summary.hasPassword||summary.has2FA);
        row.passwordCell.textContent=recorded?'••••••••':'未录入';
        row.passwordCell.setAttribute(STATUS_ATTR,recorded?'1':'0');
        row.passwordCell.title=recorded?'密码 / 2FA 已安全保存在 Vault；管理员点“查看登录资料”后可用眼睛短暂显示':'Vault 中未检测到密码或 2FA';
      }
    }
  };
  const markAccountSafeSummaryUnavailable=()=>{
    if(!isAccountAssetPage())return;
    for(const row of locateCredentialRows()){
      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'&&row.accountCell.getAttribute(LOGIN_IDENTIFIER_ATTR)!=='1'){
        matchCredentialValueTypography(row.accountCell);
        row.accountCell.textContent='状态暂不可用';
      }
    }
  };
  const clearAccountSafeSummary=()=>{
    accountSafeSummaryClientId='';
    accountSafeSummaryData=null;
    accountSafeSummaryPromise=null;
    accountSafeSummaryFetchedAt=0;
  };
  const ensureAccountSafeSummary=()=>{
    if(!isAccountAssetPage()){
      if(accountSafeSummaryData||accountSafeSummaryClientId)clearAccountSafeSummary();
      return;
    }
    if(!['ADMIN','OPS'].includes(String(vm.currentUser?.role||'')))return;
    const clientId=resolveCredentialClientId();
    if(!clientId)return;
    const now=Date.now();
    if(accountSafeSummaryData&&accountSafeSummaryClientId===clientId&&now-accountSafeSummaryFetchedAt<60000){
      applyAccountSafeSummaryToCards();
      return;
    }
    if(accountSafeSummaryPromise&&accountSafeSummaryClientId===clientId)return;
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token)return;
    if(accountSafeSummaryClientId!==clientId){
      accountSafeSummaryClientId=clientId;
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
    }
    accountSafeSummaryPromise=cloud.rpc('crm_client_account_safe_summary',{p_token:token,p_client_id:String(clientId)})
      .then(data=>{
        if(resolveCredentialClientId()!==clientId)return;
        accountSafeSummaryData=data&&typeof data==='object'?data:{};
        accountSafeSummaryFetchedAt=Date.now();
        applyAccountSafeSummaryToCards();
      })
      .catch(()=>{
        if(!accountSafeSummaryData)markAccountSafeSummaryUnavailable();
      })
      .finally(()=>{accountSafeSummaryPromise=null;});
  };
'''
security=security.replace(insert_marker,summary_helpers+insert_marker,1)

# Credential presence status RPC is FB/TK-only. Once row detection includes all four
# platforms it must not incorrectly mark Google/Instagram as unrecorded.
status_loop="    for(const row of locateCredentialRows()){\n      const status=credentialStatusData?.[row.platform]||{};\n"
if security.count(status_loop)!=1:
    raise SystemExit(f'Unexpected status row loop count: {security.count(status_loop)}')
security=security.replace(
    status_loop,
    "    for(const row of locateCredentialRows()){\n      if(!['facebook','tiktok'].includes(row.platform))continue;\n      const status=credentialStatusData?.[row.platform]||{};\n",
    1,
)

account_condition="      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'){\n"
if security.count(account_condition)<1:
    raise SystemExit('Credential account-cell condition missing')
# Only the status writer needs this guard; replace the last occurrence before ensureCredentialStatus.
status_start=security.find("  const applyCredentialStatusToCards=()=>{")
status_end=security.find("  const ensureCredentialStatus=()=>{",status_start)
status_block=security[status_start:status_end]
if status_block.count(account_condition)!=1:
    raise SystemExit(f'Unexpected status account-cell condition count: {status_block.count(account_condition)}')
status_block=status_block.replace(
    account_condition,
    "      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'&&row.accountCell.getAttribute(LOGIN_IDENTIFIER_ATTR)!=='1'){\n",
    1,
)
security=security[:status_start]+status_block+security[status_end:]

ensure_marker="    if(isAccountAssetPage())ensureCredentialStatus();\n"
if security.count(ensure_marker)!=1:
    raise SystemExit(f'Unexpected ensureCredentialStatus button marker count: {security.count(ensure_marker)}')
security=security.replace(
    ensure_marker,
    "    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();}\n    else ensureAccountSafeSummary();\n",
    1,
)

# After a full Vault reveal closes, restore the always-visible login identifier and
# masked password state rather than falling back to old template placeholders.
restore_marker="    applyCredentialStatusToCards();\n  }\n\n  function make("
if security.count(restore_marker)!=1:
    raise SystemExit(f'Unexpected reveal restore marker count: {security.count(restore_marker)}')
security=security.replace(
    restore_marker,
    "    applyCredentialStatusToCards();\n    applyAccountSafeSummaryToCards();\n  }\n\n  function make(",
    1,
)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print('ACCOUNT_LOGIN_IDENTIFIER_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
