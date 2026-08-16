from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

start=security.find("  const applyCredentialStatusToCards=()=>{")
end=security.find("  const prepareInlineCell=(cell,kind)=>{",start)
if start<0 or end<0:
    raise SystemExit('Unable to locate credential status helper block')

replacement=r'''  const credentialStatusCacheKey=clientId=>{
    const userKey=String(vm.currentUser?.id||vm.currentUser?.username||vm.currentUser?.email||'user');
    return `growthops_credential_status_v2:${userKey}:${String(clientId)}`;
  };
  const readCredentialStatusCache=clientId=>{
    try{
      const key=credentialStatusCacheKey(clientId);
      const raw=sessionStorage.getItem(key);
      if(!raw)return null;
      const cached=JSON.parse(raw);
      const savedAt=Number(cached?.savedAt||0);
      if(!cached?.data||!savedAt||Date.now()-savedAt>300000){
        sessionStorage.removeItem(key);
        return null;
      }
      return cached;
    }catch{return null}
  };
  const writeCredentialStatusCache=(clientId,data)=>{
    try{
      sessionStorage.setItem(credentialStatusCacheKey(clientId),JSON.stringify({savedAt:Date.now(),data}));
    }catch{}
  };
  const matchCredentialValueTypography=cell=>{
    if(!cell)return;
    cell.style.fontFamily='ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
    cell.style.fontSize='0.875rem';
    cell.style.lineHeight='1.25rem';
    cell.style.fontWeight='600';
  };
  const exactLeaves=(root,label)=>root?[...root.querySelectorAll('*')].filter(el=>el.children.length===0&&cleanText(el)===label):[];
  const assetSectionForHeading=(headingText)=>{
    const heading=[...document.querySelectorAll('h1,h2,h3,h4')].find(el=>cleanText(el).includes(headingText));
    if(!heading)return null;
    let node=heading.parentElement;
    for(let i=0;node&&i<8;i++,node=node.parentElement){
      const text=cleanText(node);
      if(text.includes(headingText)&&text.includes('账号名称')&&text.includes('密码 / 2FA'))return node;
    }
    return heading.parentElement;
  };
  const normalizeOtherAccountAssetTypography=()=>{
    if(!isAccountAssetPage())return;
    const specs=[
      ['Google 资产',['账号名称','Google Ads 客户 ID','MCC ID','登录邮箱','密码 / 2FA']],
      ['Instagram 资产',['账号名称','Instagram 用户名','Instagram ID','登录邮箱 / 手机号','密码 / 2FA']],
    ];
    for(const [headingText,labels] of specs){
      const section=assetSectionForHeading(headingText);
      if(!section)continue;
      for(const label of labels){
        for(const labelEl of exactLeaves(section,label)){
          const cell=valueCellForLabel(labelEl);
          if(cell)matchCredentialValueTypography(cell);
        }
      }
    }
  };
  const applyCredentialLoadingToCards=()=>{
    if(!isAccountAssetPage())return;
    normalizeOtherAccountAssetTypography();
    for(const row of locateCredentialRows()){
      for(const cell of [row.accountCell,row.passwordCell]){
        if(!cell||cell.getAttribute(INLINE_ATTR)==='1')continue;
        if(cell.getAttribute(STATUS_ATTR)==='1'||cell.getAttribute(STATUS_ATTR)==='0')continue;
        matchCredentialValueTypography(cell);
        cell.textContent='读取中…';
        cell.setAttribute(STATUS_ATTR,'loading');
        cell.title='正在安全检查 Vault 录入状态';
      }
    }
  };
  const applyCredentialStatusUnavailable=()=>{
    if(!isAccountAssetPage())return;
    normalizeOtherAccountAssetTypography();
    for(const row of locateCredentialRows()){
      for(const cell of [row.accountCell,row.passwordCell]){
        if(!cell||cell.getAttribute(INLINE_ATTR)==='1')continue;
        if(cell.getAttribute(STATUS_ATTR)!=='loading')continue;
        matchCredentialValueTypography(cell);
        cell.textContent='状态暂不可用';
        cell.setAttribute(STATUS_ATTR,'error');
        cell.title='凭证状态读取失败，请稍后刷新重试';
      }
    }
  };
  const applyCredentialStatusToCards=()=>{
    if(!isAccountAssetPage()||!credentialStatusData)return;
    normalizeOtherAccountAssetTypography();
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==credentialStatusClientId)return;
    for(const row of locateCredentialRows()){
      const status=credentialStatusData?.[row.platform]||{};
      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'){
        matchCredentialValueTypography(row.accountCell);
        if(status.hasLoginAccount){
          row.accountCell.textContent='已录入';
          row.accountCell.setAttribute(STATUS_ATTR,'1');
          row.accountCell.title='登录账号已安全保存在 Vault';
        }else{
          row.accountCell.textContent='未录入';
          row.accountCell.setAttribute(STATUS_ATTR,'0');
          row.accountCell.title='Vault 中未检测到登录账号';
        }
      }
      if(row.passwordCell&&row.passwordCell.getAttribute(INLINE_ATTR)!=='1'){
        matchCredentialValueTypography(row.passwordCell);
        if(status.hasPassword||status.has2FA){
          row.passwordCell.textContent='••••••••';
          row.passwordCell.setAttribute(STATUS_ATTR,'1');
          row.passwordCell.title='密码 / 2FA 已安全保存在 Vault；点击“查看登录资料”后可单独显示';
        }else{
          row.passwordCell.textContent='未录入';
          row.passwordCell.setAttribute(STATUS_ATTR,'0');
          row.passwordCell.title='Vault 中未检测到密码或 2FA';
        }
      }
    }
  };
  const ensureCredentialStatus=()=>{
    if(!isAccountAssetPage())return;
    normalizeOtherAccountAssetTypography();
    if(!['ADMIN','OPS'].includes(String(vm.currentUser?.role||'')))return;
    const clientId=resolveCredentialClientId();
    if(!clientId)return;
    const now=Date.now();
    if(credentialStatusData&&credentialStatusClientId===clientId&&now-credentialStatusFetchedAt<60000){
      applyCredentialStatusToCards();
      return;
    }
    if(credentialStatusPromise&&credentialStatusClientId===clientId)return;
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token)return;

    const cached=readCredentialStatusCache(clientId);
    credentialStatusClientId=clientId;
    if(cached){
      credentialStatusData=cached.data;
      credentialStatusFetchedAt=0;
      applyCredentialStatusToCards();
    }else{
      credentialStatusData=null;
      credentialStatusFetchedAt=0;
      applyCredentialLoadingToCards();
    }

    credentialStatusPromise=cloud.rpc('crm_client_credential_status',{p_token:token,p_client_id:String(clientId)})
      .then(data=>{
        if(resolveCredentialClientId()!==clientId)return;
        credentialStatusData=data&&typeof data==='object'?data:{};
        credentialStatusFetchedAt=Date.now();
        writeCredentialStatusCache(clientId,credentialStatusData);
        applyCredentialStatusToCards();
      })
      .catch(()=>{
        if(!credentialStatusData)applyCredentialStatusUnavailable();
      })
      .finally(()=>{credentialStatusPromise=null;});
  };
'''

security=security[:start]+replacement+security[end:]
security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_STATUS_LOADING_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
