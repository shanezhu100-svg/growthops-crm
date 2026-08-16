from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

const_marker="  const INLINE_ATTR='data-growthops-vault-inline';\n"
if security.count(const_marker)!=1:
    raise SystemExit(f'Unexpected inline credential marker count: {security.count(const_marker)}')
security=security.replace(
    const_marker,
    const_marker+"  const STATUS_ATTR='data-growthops-credential-status';\n",
    1,
)

state_marker="  let revealData=null;\n  let revealTimer=null;\n"
if security.count(state_marker)!=1:
    raise SystemExit(f'Unexpected reveal state marker count: {security.count(state_marker)}')
security=security.replace(
    state_marker,
    state_marker+"  let credentialStatusClientId='';\n  let credentialStatusData=null;\n  let credentialStatusPromise=null;\n  let credentialStatusFetchedAt=0;\n",
    1,
)

insert_marker="  const prepareInlineCell=(cell,kind)=>{\n"
if security.count(insert_marker)!=1:
    raise SystemExit(f'Unexpected credential row insertion marker count: {security.count(insert_marker)}')
status_helpers='''  const applyCredentialStatusToCards=()=>{
    if(!isAccountAssetPage()||!credentialStatusData)return;
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==credentialStatusClientId)return;
    for(const row of locateCredentialRows()){
      const status=credentialStatusData?.[row.platform]||{};
      if(row.accountCell&&row.accountCell.getAttribute(INLINE_ATTR)!=='1'){
        if(status.hasLoginAccount){
          row.accountCell.textContent='已录入';
          row.accountCell.setAttribute(STATUS_ATTR,'1');
          row.accountCell.title='登录账号已安全保存在 Vault';
        }else if(row.accountCell.getAttribute(STATUS_ATTR)==='1'){
          row.accountCell.textContent='未录入';
          row.accountCell.removeAttribute(STATUS_ATTR);
          row.accountCell.removeAttribute('title');
        }
      }
      if(row.passwordCell&&row.passwordCell.getAttribute(INLINE_ATTR)!=='1'){
        if(status.hasPassword||status.has2FA){
          row.passwordCell.textContent='••••••••';
          row.passwordCell.setAttribute(STATUS_ATTR,'1');
          row.passwordCell.title='密码 / 2FA 已安全保存在 Vault；点击“查看登录资料”后可单独显示';
        }else if(row.passwordCell.getAttribute(STATUS_ATTR)==='1'){
          row.passwordCell.textContent='未录入';
          row.passwordCell.removeAttribute(STATUS_ATTR);
          row.passwordCell.removeAttribute('title');
        }
      }
    }
  };
  const ensureCredentialStatus=()=>{
    if(!isAccountAssetPage())return;
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
    credentialStatusClientId=clientId;
    credentialStatusData=null;
    credentialStatusPromise=cloud.rpc('crm_client_credential_status',{p_token:token,p_client_id:String(clientId)})
      .then(data=>{
        if(resolveCredentialClientId()!==clientId)return;
        credentialStatusData=data&&typeof data==='object'?data:{};
        credentialStatusFetchedAt=Date.now();
        applyCredentialStatusToCards();
      })
      .catch(()=>{})
      .finally(()=>{credentialStatusPromise=null;});
  };
'''
security=security.replace(insert_marker,status_helpers+insert_marker,1)

ensure_marker="  function ensureRevealButton(){\n    const clientId=resolveCredentialClientId();\n"
if security.count(ensure_marker)!=1:
    raise SystemExit(f'Unexpected reveal button ensure marker count: {security.count(ensure_marker)}')
security=security.replace(
    ensure_marker,
    "  function ensureRevealButton(){\n    if(isAccountAssetPage())ensureCredentialStatus();\n    const clientId=resolveCredentialClientId();\n",
    1,
)

clear_marker="    setRevealButtonState(false);\n  }\n\n  function make("
if security.count(clear_marker)!=1:
    raise SystemExit(f'Unexpected reveal cleanup marker count: {security.count(clear_marker)}')
security=security.replace(
    clear_marker,
    "    setRevealButtonState(false);\n    applyCredentialStatusToCards();\n  }\n\n  function make(",
    1,
)

old_toggle="    const toggle=make('button',{type:'button','aria-label':'显示密码和 2FA',style:'border:0;background:transparent;color:#64748b;cursor:pointer;padding:2px 4px;font-size:12px;line-height:1;'},'👁');\n"
new_toggle="    const toggle=make('button',{type:'button','aria-label':'显示密码和 2FA',title:'显示密码和 2FA',style:'border:0;background:transparent;color:#64748b;cursor:pointer;padding:2px 4px;font-size:13px;line-height:1;'},'');\n    toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';\n"
if security.count(old_toggle)!=1:
    raise SystemExit(f'Unexpected secret eye button marker count: {security.count(old_toggle)}')
security=security.replace(old_toggle,new_toggle,1)

old_hide="      toggle.textContent='👁';\n      toggle.setAttribute('aria-label','显示密码和 2FA');\n"
new_hide="      toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';\n      toggle.setAttribute('aria-label','显示密码和 2FA');\n      toggle.setAttribute('title','显示密码和 2FA');\n"
if security.count(old_hide)!=1:
    raise SystemExit(f'Unexpected secret eye hide marker count: {security.count(old_hide)}')
security=security.replace(old_hide,new_hide,1)

old_show="      toggle.textContent='🙈';\n      toggle.setAttribute('aria-label','隐藏密码和 2FA');\n"
new_show="      toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';\n      toggle.setAttribute('aria-label','隐藏密码和 2FA');\n      toggle.setAttribute('title','隐藏密码和 2FA');\n"
if security.count(old_show)!=1:
    raise SystemExit(f'Unexpected secret eye show marker count: {security.count(old_show)}')
security=security.replace(old_show,new_show,1)

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_STATUS_UI_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
