from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

insert_marker="  const installProtectedFieldControl=(row,summary)=>{\n"
if security.count(insert_marker)!=1:
    raise SystemExit(f'Unexpected credential unlock insertion marker count: {security.count(insert_marker)}')

helpers=r'''  let credentialUnlockToken='';
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
security=security.replace(insert_marker,helpers+insert_marker,1)

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

rpc_old="""        bundle=await cloud.rpc('crm_reveal_client_secret_field_v3',{
          p_token:token,
          p_client_id:String(clientId),
"""
rpc_new="""        bundle=await cloud.rpc('crm_reveal_client_secret_field_v4',{
          p_token:token,
          p_unlock_token:unlockToken,
          p_client_id:String(clientId),
"""
if security.count(rpc_old)!=1:
    raise SystemExit(f'Unexpected v3 browser RPC count: {security.count(rpc_old)}')
security=security.replace(rpc_old,rpc_new,1)

error_marker="""    if(value.includes('FORBIDDEN'))return '只有管理员可以查看密码 / 2FA';
    return '读取密码 / 2FA 失败，请稍后重试';
"""
if security.count(error_marker)!=1:
    raise SystemExit(f'Unexpected field reveal error marker count: {security.count(error_marker)}')
security=security.replace(
    error_marker,
    """    if(value.includes('FORBIDDEN'))return '只有管理员可以查看密码 / 2FA';
    if(value.includes('CREDENTIAL_UNLOCK_REQUIRED'))return '管理员解锁已过期，请再次验证后查看';
    return '读取密码 / 2FA 失败，请稍后重试';
""",
    1,
)

catch_old="""      }catch(error){
        bundle=null;
        hide();
        vm.notify(fieldRevealErrorMessage(error));
      }
"""
catch_new="""      }catch(error){
        bundle=null;
        if(String(error?.message||error||'').includes('CREDENTIAL_UNLOCK_REQUIRED'))clearCredentialUnlock();
        hide();
        vm.notify(fieldRevealErrorMessage(error));
      }
"""
if security.count(catch_old)!=1:
    raise SystemExit(f'Unexpected per-field catch count: {security.count(catch_old)}')
security=security.replace(catch_old,catch_new,1)

visibility_old="if(document.hidden)clearReveal();"
if security.count(visibility_old)!=1:
    raise SystemExit(f'Unexpected visibility cleanup count: {security.count(visibility_old)}')
security=security.replace(visibility_old,"if(document.hidden){clearReveal();clearCredentialUnlock();}",1)

beforeunload="window.addEventListener('beforeunload',clearReveal);"
if security.count(beforeunload)!=1:
    raise SystemExit(f'Unexpected beforeunload cleanup count: {security.count(beforeunload)}')
security=security.replace(beforeunload,beforeunload+"\n  window.addEventListener('beforeunload',clearCredentialUnlock);\n  window.addEventListener('pagehide',clearCredentialUnlock);",1)

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_UNLOCK_V4_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
