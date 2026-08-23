from pathlib import Path

root = Path(__file__).resolve().parent
security_path = root / 'dist' / 'cloud-security-hotfix.js'
security = security_path.read_text(encoding='utf-8')

# Runtime repair for a stale FIELD_REVEAL_ATTR marker. The v6 preboot scrub can
# replace a credential cell's children with a placeholder while leaving the
# reveal-installed marker behind. In that state the renderer used to believe the
# eye control still existed and skipped rebuilding it.
installer_old = "    if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')return true;\n"
installer_new = """    const existingRevealControl=cell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');
    if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&existingRevealControl)return true;
    if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')cell.removeAttribute(FIELD_REVEAL_ATTR);
"""
if security.count(installer_old) != 1:
    raise SystemExit(f'Unexpected protected-field installer marker count: {security.count(installer_old)}')
security = security.replace(installer_old, installer_new, 1)

renderer_old = """        if(recorded&&vm.currentUser?.role==='ADMIN'&&row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'){
          row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
          continue;
        }
"""
renderer_new = """        const installedRevealControl=row.passwordCell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');
        if(recorded&&vm.currentUser?.role==='ADMIN'&&row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&installedRevealControl){
          row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
          continue;
        }
"""
if security.count(renderer_old) != 1:
    raise SystemExit(f'Unexpected credential renderer reveal marker count: {security.count(renderer_old)}')
security = security.replace(renderer_old, renderer_new, 1)

# The admin-unlock modal can cause the surrounding Vue credential card to be
# re-rendered while the click handler awaits crm_unlock_credentials_v1. The old
# handler then continued writing the revealed value into a detached button/cell.
# Capture the target identity before awaiting unlock. If the original control was
# detached, render the current safe-summary DOM, reacquire exactly one matching
# live row, and resume the same click using the memory-only unlock token. If the
# row cannot be matched uniquely we keep the rebuilt eye visible and require a
# second click, but never guess which account should receive a revealed secret.
unlock_old = """      const unlockToken=await ensureCredentialUnlock();
      if(!unlockToken)return;
      loading=true;
"""
unlock_new = """      const targetAccountId=accountIdForProtectedField(row)||null;
      const unlockToken=await ensureCredentialUnlock();
      if(!unlockToken)return;
      if(!cell.isConnected||!toggle.isConnected||!cell.contains(toggle)){
        requestAnimationFrame(()=>{
          credentialUiV5Render();
          const targetId=String(targetAccountId||'');
          const liveRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform&&String(accountIdForProtectedField(candidate)||'')===targetId);
          const liveRow=liveRows.length===1?liveRows[0]:null;
          const liveToggle=liveRow?.passwordCell?.querySelector('button[aria-label=\"显示密码和 2FA\"]');
          if(liveToggle){liveToggle.click();return;}
          vm.notify('管理员验证成功；凭证区域已刷新，请再次点击眼睛查看');
        });
        return;
      }
      loading=true;
"""
if security.count(unlock_old) != 1:
    raise SystemExit(f'Unexpected unlock continuation marker count: {security.count(unlock_old)}')
security = security.replace(unlock_old, unlock_new, 1)

# Keep the reveal bound to the account identity captured before the unlock await.
account_old = "        const accountId=accountIdForProtectedField(row)||null;\n"
account_new = "        const accountId=targetAccountId;\n"
if security.count(account_old) != 1:
    raise SystemExit(f'Unexpected scalar reveal account marker count: {security.count(account_old)}')
security = security.replace(account_old, account_new, 1)

# A second DOM replacement can happen after the scalar v5 calls complete. Keep the
# visible value only in this page's memory for the same 10-second window already
# used by the field control. The cache is scoped by client + platform + account,
# never persisted, and is cleared on hide/background/navigation. A newly rendered
# matching cell can therefore rehydrate the same short-lived display without
# re-fetching or exposing a different account's secret.
ephemeral_insert = "  const installProtectedFieldControl=(row,summary)=>{\n"
if security.count(ephemeral_insert) != 1:
    raise SystemExit(f'Unexpected protected-field installer insertion count: {security.count(ephemeral_insert)}')
ephemeral_helpers = r'''  const credentialEphemeralReveals=new Map();
  const credentialEphemeralRevealKey=row=>{
    const clientId=String(resolveCredentialClientId()||'');
    const platform=String(row?.platform||'');
    const accountId=String(accountIdForProtectedField(row)||'');
    return clientId&&platform&&accountId?JSON.stringify([clientId,platform,accountId]):'';
  };
  const clearCredentialEphemeralReveals=()=>{
    for(const cell of document.querySelectorAll(`[${FIELD_REVEAL_ATTR}="1"]`)){
      try{if(typeof cell.__growthOpsVaultFieldClear==='function')cell.__growthOpsVaultFieldClear();}catch{}
    }
    credentialEphemeralReveals.clear();
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearCredentialEphemeralReveals();});
  window.addEventListener('pagehide',clearCredentialEphemeralReveals);
  window.addEventListener('beforeunload',clearCredentialEphemeralReveals);

'''
security = security.replace(ephemeral_insert, ephemeral_helpers + ephemeral_insert, 1)

cell_guard_old = """    const cell=row?.passwordCell;
    if(!cell||!protectedFieldRecorded(row,summary))return false;
"""
cell_guard_new = """    const cell=row?.passwordCell;
    if(!cell||!protectedFieldRecorded(row,summary))return false;
    const revealKey=credentialEphemeralRevealKey(row);
"""
if security.count(cell_guard_old) != 1:
    raise SystemExit(f'Unexpected protected-field cell guard count: {security.count(cell_guard_old)}')
security = security.replace(cell_guard_old, cell_guard_new, 1)

hide_old = """    const hide=()=>{
      clearTimeout(fieldTimer);
      fieldTimer=null;
      visibleValue='';
      display.textContent='••••••••';
"""
hide_new = """    const hide=()=>{
      clearTimeout(fieldTimer);
      fieldTimer=null;
      if(revealKey)credentialEphemeralReveals.delete(revealKey);
      visibleValue='';
      display.textContent='••••••••';
      if(cell.isConnected)cell.setAttribute('data-growthops-credential-v5-state','ready');
"""
if security.count(hide_old) != 1:
    raise SystemExit(f'Unexpected protected-field hide block count: {security.count(hide_old)}')
security = security.replace(hide_old, hide_new, 1)

success_old = """        if(!visibleValue){
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
"""
success_new = """        if(!visibleValue){
          vm.notify('该账号当前没有可显示的密码 / 2FA');
          hide();
          return;
        }
        if(document.hidden||!isCredentialSummaryContext()||resolveCredentialClientId()!==clientId){
          visibleValue='';
          hide();
          return;
        }
        const revealExpiresAt=Date.now()+10000;
        if(revealKey)credentialEphemeralReveals.set(revealKey,{value:visibleValue,expiresAt:revealExpiresAt});
        display.textContent=visibleValue;
        cell.setAttribute('data-growthops-credential-v5-state','revealed');
        toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';
        toggle.setAttribute('aria-label','隐藏密码和 2FA');
        toggle.disabled=false;
        loading=false;
        fieldTimer=setTimeout(hide,10000);
        requestAnimationFrame(()=>credentialUiV5Render());
"""
if security.count(success_old) != 1:
    raise SystemExit(f'Unexpected scalar reveal success block count: {security.count(success_old)}')
security = security.replace(success_old, success_new, 1)

# Anchor on the final-output property assignment only. Earlier finalizers can
# rewrite nearby title text, but this assignment remains the stable ownership
# hook for the per-field control.
rehydrate_marker = "    cell.__growthOpsVaultFieldClear=hide;\n"
rehydrate_insert = """    const activeReveal=revealKey?credentialEphemeralReveals.get(revealKey):null;
    const now=Date.now();
    if(activeReveal&&activeReveal.value&&activeReveal.expiresAt>now&&!document.hidden){
      visibleValue=String(activeReveal.value);
      display.textContent=visibleValue;
      cell.setAttribute('data-growthops-credential-v5-state','revealed');
      toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';
      toggle.setAttribute('aria-label','隐藏密码和 2FA');
      fieldTimer=setTimeout(hide,Math.max(1,Math.min(10000,activeReveal.expiresAt-now)));
    }else if(activeReveal){
      credentialEphemeralReveals.delete(revealKey);
    }
"""
if security.count(rehydrate_marker) != 1:
    raise SystemExit(f'Unexpected protected-field ownership marker count: {security.count(rehydrate_marker)}')
security = security.replace(rehydrate_marker, rehydrate_marker + rehydrate_insert, 1)

for required in (
    "const existingRevealControl=cell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&existingRevealControl)return true;",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')cell.removeAttribute(FIELD_REVEAL_ATTR);",
    "const installedRevealControl=row.passwordCell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&installedRevealControl",
    "const targetAccountId=accountIdForProtectedField(row)||null;",
    "if(!cell.isConnected||!toggle.isConnected||!cell.contains(toggle))",
    "const liveRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform&&String(accountIdForProtectedField(candidate)||'')===targetId);",
    "const liveRow=liveRows.length===1?liveRows[0]:null;",
    "if(liveToggle){liveToggle.click();return;}",
    "const accountId=targetAccountId;",
    "const credentialEphemeralReveals=new Map();",
    "return clientId&&platform&&accountId?JSON.stringify([clientId,platform,accountId]):'';",
    "credentialEphemeralReveals.set(revealKey,{value:visibleValue,expiresAt:revealExpiresAt});",
    "const activeReveal=revealKey?credentialEphemeralReveals.get(revealKey):null;",
    "fieldTimer=setTimeout(hide,Math.max(1,Math.min(10000,activeReveal.expiresAt-now)));",
    "document.addEventListener('visibilitychange',()=>{if(document.hidden)clearCredentialEphemeralReveals();});",
    "window.addEventListener('pagehide',clearCredentialEphemeralReveals);",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "setTimeout(hide,10000)",
):
    if required not in security:
        raise SystemExit(f'Credential eye self-heal marker missing: {required}')

for forbidden in (
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "localStorage.setItem('growthops_credential",
    "sessionStorage.setItem('growthops_credential",
):
    if forbidden in security:
        raise SystemExit(f'Legacy/persistent credential reveal path unexpectedly present: {forbidden}')

security_path.write_text(security, encoding='utf-8')
print('CREDENTIAL_EYE_SELF_HEAL_FINALIZE_OK: stale-marker=repair; unlock-rerender=reacquire-live-row; post-reveal-rerender=ephemeral-10s-rehydrate; persistence=none; reveal=v5-scalar')
