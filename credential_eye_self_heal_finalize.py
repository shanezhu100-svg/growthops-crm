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

for required in (
    "const existingRevealControl=cell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&existingRevealControl)return true;",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')cell.removeAttribute(FIELD_REVEAL_ATTR);",
    "const installedRevealControl=row.passwordCell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&installedRevealControl",
    "const targetAccountId=accountIdForProtectedField(row)||null;",
    "if(!cell.isConnected||!toggle.isConnected||!cell.contains(toggle))",
    "requestAnimationFrame(()=>{",
    "credentialUiV5Render();",
    "const liveRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform&&String(accountIdForProtectedField(candidate)||'')===targetId);",
    "const liveRow=liveRows.length===1?liveRows[0]:null;",
    "if(liveToggle){liveToggle.click();return;}",
    "const accountId=targetAccountId;",
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
):
    if forbidden in security:
        raise SystemExit(f'Legacy credential reveal path unexpectedly present: {forbidden}')

security_path.write_text(security, encoding='utf-8')
print('CREDENTIAL_EYE_SELF_HEAL_FINALIZE_OK: stale-marker=repair; unlock-rerender=reacquire-live-row; reveal=v5-scalar; account-binding=pre-unlock')
