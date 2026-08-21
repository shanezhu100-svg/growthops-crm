from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

# Phase 2 refactor: collapse the historical credential reveal v3 -> unlock v4
# build stages into one in-memory transformation. The intermediate broader v3
# browser transport is never written to dist; only the least-privilege final
# controller is persisted.
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
    if(vm.currentUser?.role!=='ADMIN'||!isAccountAssetPage()||!accountSafeSummaryData)return;
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==accountSafeSummaryClientId)return;
    for(const row of locateCredentialRows()){
      const summary=summaryForCredentialRow(row)||{};
      if(protectedFieldRecorded(row,summary))installProtectedFieldControl(row,summary);
    }
  };

'''
security=security.replace(insert_marker,helpers+insert_marker,1)

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

button_marker="    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();}\n    else ensureAccountSafeSummary();\n"
if security.count(button_marker)!=1:
    raise SystemExit(f'Unexpected account asset ensure marker count: {security.count(button_marker)}')
security=security.replace(
    button_marker,
    "    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();installProtectedFieldControls();}\n    else ensureAccountSafeSummary();\n",
    1,
)

clear_marker="      el.removeAttribute('data-growthops-vault-kind');\n"
if security.count(clear_marker)!=1:
    raise SystemExit(f'Unexpected clear field marker count: {security.count(clear_marker)}')
security=security.replace(
    clear_marker,
    clear_marker+"      el.removeAttribute(FIELD_REVEAL_ATTR);\n",
    1,
)

# In-memory upgrade to the final unlock + scalar-value reveal transport. Unlike the
# historical two-file chain, the broader v3 browser transport above is never written
# to dist and therefore cannot become a build artifact.
insert_marker="  const installProtectedFieldControl=(row,summary)=>{\n"
if security.count(insert_marker)!=1:
    raise SystemExit(f'Unexpected credential unlock insertion marker count: {security.count(insert_marker)}')

unlock_helpers=r'''  let credentialUnlockToken='';
  let credentialUnlockExpiresAt=0;
  let credentialUnlockUserId='';
  let credentialUnlockPromptPromise=null;
  const clearCredentialUnlock=()=>{
    credentialUnlockToken='';
    credentialUnlockExpiresAt=0;
    credentialUnlockUserId='';
  };
  const hasCredentialUnlock=()=>{
    const userId=String(vm.currentUser?.id||'');
    if(!userId||credentialUnlockUserId!==userId){
      clearCredentialUnlock();
      return false;
    }
    if(!credentialUnlockToken||credentialUnlockExpiresAt<=Date.now()+3000){
      clearCredentialUnlock();
      return false;
    }
    return true;
  };
  const credentialUnlockErrorMessage=error=>{
    const value=String(error?.message||error||'');
    if(value.includes('CREDENTIAL_UNLOCK_INVALID'))return '管理员密码不正确，请重新输入';
    if(value.includes('CREDENTIAL_UNLOCK_THROTTLED'))return '验证失败次数过多，请稍后再试';
    if(value.includes('FORBIDDEN'))return '只有管理员可以解锁密码查看';
    return '管理员身份验证失败，请稍后重试';
  };
  const requestCredentialUnlock=()=>{
    if(hasCredentialUnlock())return Promise.resolve(credentialUnlockToken);
    if(credentialUnlockPromptPromise)return credentialUnlockPromptPromise;
    credentialUnlockPromptPromise=new Promise(resolve=>{
      const overlay=make('div',{style:'position:fixed;inset:0;z-index:2147483640;background:rgba(15,23,42,.5);display:flex;align-items:center;justify-content:center;padding:20px;'});
      const card=make('div',{style:'width:min(400px,94vw);background:#fff;border-radius:18px;box-shadow:0 24px 70px rgba(15,23,42,.28);padding:22px;color:#0f172a;font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;'});
      const title=make('div',{style:'font-size:17px;font-weight:800;margin-bottom:7px;'},'验证管理员身份');
      const desc=make('div',{style:'color:#64748b;font-size:12px;line-height:1.6;margin-bottom:16px;'},'查看客户密码 / 2FA 前，请输入当前管理员登录密码。验证成功后，本标签页 10 分钟内无需重复输入；切换后台或关闭页面会立即失效。');
      const form=make('form');
      const input=make('input',{type:'password',autocomplete:'off',spellcheck:'false','aria-label':'管理员登录密码',placeholder:'请输入当前管理员登录密码',style:'width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:11px;padding:11px 12px;font:14px/1.3 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;outline:none;'});
      const errorBox=make('div',{style:'min-height:18px;margin-top:7px;color:#dc2626;font-size:12px;'});
      const actions=make('div',{style:'display:flex;justify-content:flex-end;gap:8px;margin-top:15px;'});
      const cancel=make('button',{type:'button',style:'border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:10px;padding:8px 13px;cursor:pointer;font-weight:700;'},'取消');
      const submit=make('button',{type:'submit',style:'border:0;background:#0f172a;color:#fff;border-radius:10px;padding:8px 14px;cursor:pointer;font-weight:750;'},'验证并解锁');
      actions.appendChild(cancel);
      actions.appendChild(submit);
      form.appendChild(input);
      form.appendChild(errorBox);
      form.appendChild(actions);
      card.appendChild(title);
      card.appendChild(desc);
      card.appendChild(form);
      overlay.appendChild(card);

      let settled=false;
      const finish=value=>{
        if(settled)return;
        settled=true;
        input.value='';
        overlay.remove();
        credentialUnlockPromptPromise=null;
        resolve(value||'');
      };
      cancel.addEventListener('click',()=>finish(''));
      overlay.addEventListener('click',event=>{if(event.target===overlay)finish('');});
      form.addEventListener('submit',async event=>{
        event.preventDefault();
        if(submit.disabled)return;
        let password=input.value;
        input.value='';
        if(!password){
          errorBox.textContent='请输入管理员登录密码';
          input.focus();
          return;
        }
        const token=localStorage.getItem(TOKEN_KEY)||'';
        if(!token){
          password='';
          errorBox.textContent='当前会话已失效，请重新登录';
          return;
        }
        submit.disabled=true;
        cancel.disabled=true;
        submit.textContent='验证中…';
        errorBox.textContent='';
        try{
          const data=await cloud.rpc('crm_unlock_credentials_v1',{p_token:token,p_password:password});
          password='';
          const unlockToken=String(data?.unlockToken||'');
          const expiresAt=Date.parse(String(data?.expiresAt||''));
          if(!unlockToken)throw new Error('CREDENTIAL_UNLOCK_EMPTY');
          credentialUnlockToken=unlockToken;
          credentialUnlockExpiresAt=Number.isFinite(expiresAt)?expiresAt:Date.now()+600000;
          credentialUnlockUserId=String(vm.currentUser?.id||'');
          finish(credentialUnlockToken);
        }catch(error){
          password='';
          clearCredentialUnlock();
          submit.disabled=false;
          cancel.disabled=false;
          submit.textContent='验证并解锁';
          errorBox.textContent=credentialUnlockErrorMessage(error);
          input.focus();
        }
      });

      document.body.appendChild(overlay);
      queueMicrotask(()=>input.focus());
    });
    return credentialUnlockPromptPromise;
  };
  const ensureCredentialUnlock=async()=>hasCredentialUnlock()?credentialUnlockToken:await requestCredentialUnlock();

'''
security=security.replace(insert_marker,unlock_helpers+insert_marker,1)

unlock_after_token="""      if(!clientId||!token){
        vm.notify('当前会话已失效，请重新登录');
        return;
      }
      loading=true;
"""
if security.count(unlock_after_token)!=1:
    raise SystemExit(f'Unexpected per-field token guard count: {security.count(unlock_after_token)}')
security=security.replace(
    unlock_after_token,
    """      if(!clientId||!token){
        vm.notify('当前会话已失效，请重新登录');
        return;
      }
      const unlockToken=await ensureCredentialUnlock();
      if(!unlockToken)return;
      loading=true;
""",
    1,
)

reveal_old="""      let bundle=null;
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
        toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';
        toggle.setAttribute('aria-label','隐藏密码和 2FA');
        toggle.disabled=false;
        loading=false;
        fieldTimer=setTimeout(hide,10000);
      }catch(error){
        bundle=null;
        hide();
        vm.notify(fieldRevealErrorMessage(error));
      }
"""
reveal_new="""      try{
        const accountId=accountIdForProtectedField(row)||null;
        const revealValue=async field=>{
          const data=await cloud.rpc('crm_reveal_client_secret_value_v5',{
            p_token:token,
            p_unlock_token:unlockToken,
            p_client_id:String(clientId),
            p_platform:String(row.platform||''),
            p_account_id:accountId,
            p_field:field
          });
          return String(data?.value||'');
        };
        let password='';
        let twofa='';
        if(summary?.hasPassword)password=await revealValue('password');
        if(summary?.has2FA)twofa=await revealValue('twofa');
        const secureParts=[];
        if(password)secureParts.push(password);
        if(twofa)secureParts.push(`2FA: ${twofa}`);
        visibleValue=secureParts.join('  ·  ');
        password='';
        twofa='';
        if(!visibleValue){
          vm.notify('该账号当前没有可显示的密码 / 2FA');
          hide();
          return;
        }
        display.textContent=visibleValue;
        toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';
        toggle.setAttribute('aria-label','隐藏密码和 2FA');
        toggle.disabled=false;
        loading=false;
        fieldTimer=setTimeout(hide,10000);
      }catch(error){
        if(String(error?.message||error||'').includes('CREDENTIAL_UNLOCK_REQUIRED'))clearCredentialUnlock();
        hide();
        vm.notify(fieldRevealErrorMessage(error));
      }
"""
if security.count(reveal_old)!=1:
    raise SystemExit(f'Unexpected v3 bundle reveal block count: {security.count(reveal_old)}')
security=security.replace(reveal_old,reveal_new,1)

error_marker="""    if(value.includes('FORBIDDEN'))return '只有管理员可以查看密码 / 2FA';
    return '读取密码 / 2FA 失败，请稍后重试';
"""
if security.count(error_marker)!=1:
    raise SystemExit(f'Unexpected field reveal error marker count: {security.count(error_marker)}')
security=security.replace(
    error_marker,
    """    if(value.includes('FORBIDDEN'))return '只有管理员可以查看密码 / 2FA';
    if(value.includes('CREDENTIAL_UNLOCK_REQUIRED'))return '管理员解锁已过期，请再次验证后查看';
    if(value.includes('INVALID_CREDENTIAL_FIELD'))return '凭证字段请求无效';
    return '读取密码 / 2FA 失败，请稍后重试';
""",
    1,
)

visibility_old="if(document.hidden)clearReveal();"
if security.count(visibility_old)!=1:
    raise SystemExit(f'Unexpected visibility cleanup count: {security.count(visibility_old)}')
security=security.replace(visibility_old,"if(document.hidden){clearReveal();clearCredentialUnlock();}",1)

beforeunload="window.addEventListener('beforeunload',clearReveal);"
if security.count(beforeunload)!=1:
    raise SystemExit(f'Unexpected beforeunload cleanup count: {security.count(beforeunload)}')
security=security.replace(beforeunload,beforeunload+"\n  window.addEventListener('beforeunload',clearCredentialUnlock);\n  window.addEventListener('pagehide',clearCredentialUnlock);",1)

for forbidden in (
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "flattenSecretFields(bundle",
):
    if forbidden in security:
        raise SystemExit(f'Broader credential reveal path survived secure finalization: {forbidden}')
for required in (
    "cloud.rpc('crm_reveal_client_secret_value_v5'",
    "p_field:field",
    "if(summary?.hasPassword)password=await revealValue('password')",
    "if(summary?.has2FA)twofa=await revealValue('twofa')",
):
    if required not in security:
        raise SystemExit(f'Minimal credential reveal marker missing: {required}')

# Byte-for-byte compatibility gate against the production output immediately after
# the historical v4 stage. Remove/update this only when intentionally changing the
# credential controller rather than refactoring its build path.
EXPECTED_SECURITY_SHA256='3193ab24928672b0ba6f0cd0f9a8ab572646d8cf7b69aa48accbe1349231022e'
actual=hashlib.sha256(security.encode('utf-8')).hexdigest()
if actual!=EXPECTED_SECURITY_SHA256:
    raise SystemExit(f'Credential reveal refactor changed output unexpectedly: {actual} != {EXPECTED_SECURITY_SHA256}')

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_SECURE_REVEAL_FINALIZE_OK: reveal_transport=v5-single-value; security='+actual)
