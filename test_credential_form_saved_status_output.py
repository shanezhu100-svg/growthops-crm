from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'

html = INDEX.read_text(encoding='utf-8')
security = SECURITY.read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit('CREDENTIAL_FORM_SAVED_STATUS_OUTPUT_FAILED: ' + message)


# The client edit form still owns empty mutation inputs. Saved Vault values must
# never be copied back into the Vue model or browser form automatically.
for marker in (
    'account.loginAccount',
    'account.loginPassword',
    '登录账号',
    '密码 / 2FA',
    'client-form',
):
    require(marker in html, 'client form marker missing: ' + marker)

for marker in (
    "vm.currentPage==='client-form'",
    "if(vm.currentPage==='client-detail'||vm.currentPage==='client-form')",
    'const directCandidates=[vm.selectedClientId,vm.selectedClient?.id,vm.currentClient?.id]',
    "if(text&&text!=='0'&&text.toUpperCase()!=='ALL')return text",
    'const explicitAssetsClientId=vm.selectedAssetsClientId',
    "if(explicitAssetsClientText==='0'||explicitAssetsClientText.toUpperCase()==='ALL')return ''",
    'credentialLabelCount',
    "credentialLabelCount(node,'登录账号')===1",
    "credentialLabelCount(node,'密码 / 2FA')===1",
    "const platformForCard=card=>{",
    "for(let i=0;node&&i<9;i+=1,node=node.parentElement)",
    'configureCredentialFormOverlay',
    'credentialFormStatusHost',
    "data-growthops-credential-form-status",
    "data-growthops-credential-form-input",
    "data-growthops-credential-original-placeholder",
    "host.setAttribute('aria-live','polite')",
    "control.insertAdjacentElement('afterend',host)",
    "host.className='growthops-credential-inline'",
    "position:'absolute'",
    "overflow:kind==='secret'?'visible':'hidden'",
    "host.style.left=`${Math.max(0,controlRect.left-parentRect.left+14)}px`",
    "host.style.height=`${Math.max(1,controlRect.height)}px`",
    "host.__growthOpsCredentialFormControl=control",
    "host.__growthOpsCredentialFormSync=sync",
    "host.addEventListener('mousedown'",
    "control.addEventListener('focus',sync)",
    "control.addEventListener('input',sync)",
    "control.addEventListener('blur',()=>queueMicrotask(sync))",
    "const editing=String(control.value||'')!==''",
    "control.setAttribute('placeholder',visible?'':original)",
    "button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]",
    "display:'inline-flex'",
    "flex:'0 0 auto'",
    "minWidth:'26px'",
    "minHeight:'26px'",
    "formStatus=row.accountCell.getAttribute('data-growthops-credential-form-status')==='account'",
    "row.accountCell.textContent=formStatus?(login||''):(login||'未录入')",
    "row.accountCell.__growthOpsCredentialFormSync?.()",
    "formSecretStatus=row.passwordCell.getAttribute('data-growthops-credential-form-status')==='secret'",
    "row.passwordCell.textContent=formSecretStatus?'':'未录入'",
    "row.passwordCell.textContent='••••••••'",
    "row.passwordCell.__growthOpsCredentialFormSync?.()",
    'installProtectedFieldControl(row,summary)',
    "cloud.rpc('crm_client_account_safe_summary'",
    "cloud.rpc('crm_reveal_client_secret_value_v5'",
):
    require(marker in security, 'saved credential form behavior missing: ' + marker)

# Focus alone must never be interpreted as mutation. This exact old expression is
# the regression that made the saved account disappear immediately on click.
require(
    "document.activeElement===control||String(control.value||'')!==''" not in security,
    'focus is still incorrectly treated as credential edit',
)

# The old below-input presentation and `已保存：` prefix must be gone.
for forbidden in (
    "host.className='growthops-credential-inline text-[11px] text-slate-500 mt-1'",
    "login?`已保存：${login}`",
    "safe-summary=sibling-status",
):
    require(forbidden not in security, 'legacy below-input saved credential UI remains: ' + forbidden)

# Multiple Facebook/TikTok accounts must resolve at the nearest card containing
# exactly one credential-label pair; platform detection may climb to the section
# header even when the account's custom display name contains no platform text.
require(
    "if(value.includes('facebook'))return 'facebook';" in security
    and "if(value.includes('tiktok'))return 'tiktok';" in security,
    'platform ancestry resolver missing',
)

# Explicitly fail if any future change starts hydrating plaintext Vault values into
# the edit controls or Vue account model. The in-input visual is overlay-only.
for forbidden in (
    '.value=login',
    '.value=password',
    '.value=twofa',
    'loginPassword=value',
    'loginAccount=value',
    'account.loginPassword=',
    'account.loginAccount=',
):
    require(forbidden not in security, 'plaintext form hydration path present: ' + forbidden)

require("setTimeout(hide,10000)" in security, 'per-field reveal must remain time bounded')
require('navigator.clipboard' not in security, 'credential UI must not auto-copy secrets')

print(
    'CREDENTIAL_FORM_SAVED_STATUS_OUTPUT_OK: '
    'client-form=safe-summary-enabled+direct-client-id-before-asset-sentinel; '
    'login=input-overlay+focus-preserved; password-2fa=input-overlay+masked+visible-eye-hit-target; '
    'typing=mutation-handoff; empty-form-status=original-placeholder; '
    'form-inputs=mutation-only; plaintext-hydration=none; multi-account-card=nearest-pair'
)
