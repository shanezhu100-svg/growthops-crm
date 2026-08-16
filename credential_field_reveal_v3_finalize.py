from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

const_marker="  const LOGIN_IDENTIFIER_ATTR='data-growthops-login-identifier';\n"
if security.count(const_marker)!=1:
    raise SystemExit(f'Unexpected login identifier attr marker count: {security.count(const_marker)}')
security=security.replace(
    const_marker,
    const_marker+"  const FIELD_REVEAL_ATTR='data-growthops-field-reveal';\n",
    1,
)

insert_marker="  const applyCredentialLoadingToCards=()=>{\n"
if security.count(insert_marker)!=1:
    raise SystemExit(f'Unexpected protected field insertion marker count: {security.count(insert_marker)}')
helpers=r'''  const assetClientForProtectedField=()=>vm.selectedAssetsClient||vm.selectedClient||vm.currentClient||vm.assetClient||{};
  const accountIdForProtectedField=row=>{
    const client=assetClientForProtectedField();
    const key=row.platform==='facebook'?'fbAccounts':row.platform==='tiktok'?'tkAccounts':row.platform==='google'?'googleAccounts':'instagramAccounts';
    const list=Array.isArray(client?.[key])?client[key]:[];
    if(!list.length)return '';
    if(list.length===1)return String(list[0]?.id??'');
    const cardText=String(row?.card?.textContent||'');
    const match=list.find(item=>item?.id!=null&&cardText.includes(String(item.id)));
    return match?.id!=null?String(match.id):'';
  };
  const protectedFieldRecorded=(row,summary)=>Boolean(summary?.hasPassword||summary?.has2FA);
  const fieldRevealErrorMessage=error=>{
    const value=String(error?.message||error||'');
    if(value.includes('CREDENTIAL_REAUTH_REQUIRED'))return '当前登录已超过敏感凭证查看时限，请重新登录后再查看密码';
    if(value.includes('CREDENTIAL_REVEAL_THROTTLED'))return '密码查看操作过于频繁，请稍后再试';
    if(value.includes('FORBIDDEN'))return '只有管理员可以查看密码 / 2FA';
    return '读取密码 / 2FA 失败，请稍后重试';
  };
  const installProtectedFieldControl=(row,summary)=>{
    const cell=row?.passwordCell;
    if(!cell||!protectedFieldRecorded(row,summary))return false;
    if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')return true;
    if(!prepareInlineCell(cell,'field-reveal-v3'))return false;
    cell.setAttribute(FIELD_REVEAL_ATTR,'1');
    cell.textContent='';
    const wrap=make('span',{style:'display:inline-flex;align-items:center;gap:8px;max-width:100%;'});
    const display=make('span',{style:'font:inherit;word-break:break-all;'},'••••••••');
    const toggle=make('button',{type:'button','aria-label':'显示密码和 2FA',title:'仅在点击后从 Vault 读取当前账号密码，10 秒后自动隐藏',style:'border:0;background:transparent;color:#64748b;cursor:pointer;padding:2px 4px;font-size:12px;line-height:1;'});
    toggle.innerHTML='<i class="fa-regular fa-eye"></i>';
    let visibleValue='';
    let fieldTimer=null;
    let loading=false;
    const hide=()=>{
      clearTimeout(fieldTimer);
      fieldTimer=null;
      visibleValue='';
      display.textContent='••••••••';
      toggle.innerHTML='<i class="fa-regular fa-eye"></i>';
      toggle.setAttribute('aria-label','显示密码和 2FA');
      toggle.disabled=false;
      loading=false;
    };
    toggle.addEventListener('click',async event=>{
      event.preventDefault();
      event.stopPropagation();
      if(visibleValue){hide();return;}
      if(loading)return;
      if(vm.currentUser?.role!=='ADMIN'){
        vm.notify('只有管理员可以查看密码 / 2FA');
        return;
      }
      const clientId=resolveCredentialClientId();
      const token=localStorage.getItem(TOKEN_KEY)||'';
      if(!clientId||!token){
        vm.notify('当前会话已失效，请重新登录');
        return;
      }
      loading=true;
      toggle.disabled=true;
      toggle.innerHTML='<i class="fa-solid fa-spinner fa-spin"></i>';
      let bundle=null;
      try{
        bundle=await cloud.rpc('crm_reveal_client_secret_field_v3',{
          p_token:token,
          p_client_id:String(clientId),
          p_platform:String(row.platform||''),
          p_account_id:accountIdForProtectedField(row)||null
        });
        const fields=flattenSecretFields(bundle&&typeof bundle==='object'?bundle:{});
        const password=bestSecretValue(fields,row.platform,'password',row.card);
        const twofa=bestSecretValue(fields,row.platform,'twofa',row.card);
        const secureParts=[];
        if(password)secureParts.push(password);
        if(twofa)secureParts.push(`2FA: ${twofa}`);
        visibleValue=secureParts.join('  ·  ');
        bundle=null;
        fields.length=0;
        if(!visibleValue){
          vm.notify('该账号当前没有可显示的密码 / 2FA');
          hide();
          return;
        }
        display.textContent=visibleValue;
        toggle.innerHTML='<i class="fa-regular fa-eye-slash"></i>';
        toggle.setAttribute('aria-label','隐藏密码和 2FA');
        toggle.disabled=false;
        loading=false;
        fieldTimer=setTimeout(hide,10000);
      }catch(error){
        bundle=null;
        hide();
        vm.notify(fieldRevealErrorMessage(error));
      }
    });
    wrap.appendChild(display);
    wrap.appendChild(toggle);
    cell.appendChild(wrap);
    cell.title='密码 / 2FA 安全保存在 Vault；点击眼睛时仅读取当前账号，10 秒后自动隐藏';
    cell.__growthOpsVaultFieldClear=hide;
    return true;
  };
  const installProtectedFieldControls=()=>{
    if(!isAccountAssetPage()||!accountSafeSummaryData)return;
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==accountSafeSummaryClientId)return;
    for(const row of locateCredentialRows()){
      const summary=summaryForCredentialRow(row)||{};
      if(protectedFieldRecorded(row,summary))installProtectedFieldControl(row,summary);
    }
  };

'''
security=security.replace(insert_marker,helpers+insert_marker,1)

# On the account-asset page the header action must no longer fetch the full client
# secret tree. Keep the legacy full reveal only for client-detail as a compatibility
# fallback until that page is migrated to per-field reveal as well.
legacy_marker='  async function revealSelectedClient(){\n'
if security.count(legacy_marker)!=1:
    raise SystemExit(f'Unexpected revealSelectedClient marker count: {security.count(legacy_marker)}')
security=security.replace(legacy_marker,'  async function revealSelectedClientLegacy(){\n',1)
ensure_marker='  function ensureRevealButton(){\n'
if security.count(ensure_marker)!=1:
    raise SystemExit(f'Unexpected ensureRevealButton marker count: {security.count(ensure_marker)}')
wrapper=r'''  async function revealSelectedClient(){
    if(isAccountAssetPage()){
      if(vm.currentUser?.role!=='ADMIN'){
        vm.notify('只有管理员可以查看密码 / 2FA');
        return;
      }
      ensureAccountSafeSummary();
      installProtectedFieldControls();
      vm.notify('登录账号 / 邮箱已显示；密码 / 2FA 请点击对应眼睛短暂查看');
      return;
    }
    return revealSelectedClientLegacy();
  }

'''
security=security.replace(ensure_marker,wrapper+ensure_marker,1)

# Install eye controls after each safe-summary refresh. prepareInlineCell marks the
# cell with INLINE_ATTR, so cached summary/status writers will not overwrite an
# active 10-second reveal.
button_marker="    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();}\n    else ensureAccountSafeSummary();\n"
if security.count(button_marker)!=1:
    raise SystemExit(f'Unexpected account asset ensure marker count: {security.count(button_marker)}')
security=security.replace(
    button_marker,
    "    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();installProtectedFieldControls();}\n    else ensureAccountSafeSummary();\n",
    1,
)

# When clearReveal removes inline controls, clear the field-specific marker too.
clear_marker="      el.removeAttribute('data-growthops-vault-kind');\n"
if security.count(clear_marker)!=1:
    raise SystemExit(f'Unexpected clear field marker count: {security.count(clear_marker)}')
security=security.replace(
    clear_marker,
    clear_marker+"      el.removeAttribute(FIELD_REVEAL_ATTR);\n",
    1,
)

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_FIELD_REVEAL_V3_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
