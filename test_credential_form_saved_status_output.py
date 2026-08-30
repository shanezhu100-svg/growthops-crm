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
    'credentialLabelCount',
    "credentialLabelCount(node,'登录账号')===1",
    "credentialLabelCount(node,'密码 / 2FA')===1",
    "const platformForCard=card=>{",
    "for(let i=0;node&&i<9;i+=1,node=node.parentElement)",
    'credentialFormStatusHost',
    "data-growthops-credential-form-status",
    "host.setAttribute('aria-live','polite')",
    "control.insertAdjacentElement('afterend',host)",
    "host.className='growthops-credential-inline text-[11px] text-slate-500 mt-1'",
    "formStatus=row.accountCell.getAttribute('data-growthops-credential-form-status')==='account'",
    "login?`已保存：${login}`:'未录入'",
    "row.passwordCell.textContent='••••••••'",
    'installProtectedFieldControl(row,summary)',
    "cloud.rpc('crm_client_account_safe_summary'",
    "cloud.rpc('crm_reveal_client_secret_value_v5'",
):
    require(marker in security, 'saved credential form behavior missing: ' + marker)

# Multiple Facebook/TikTok accounts must resolve at the nearest card containing
# exactly one credential-label pair; platform detection may climb to the section
# header even when the account's custom display name contains no platform text.
require(
    "if(value.includes('facebook'))return 'facebook';" in security
    and "if(value.includes('tiktok'))return 'tiktok';" in security,
    'platform ancestry resolver missing',
)

# Explicitly fail if any future change starts hydrating plaintext Vault values into
# the edit controls or Vue account model. Reveal remains a sibling status surface.
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
    'client-form=safe-summary-enabled; login=saved-status; password-2fa=masked+scalar-eye; '
    'form-inputs=mutation-only; plaintext-hydration=none; multi-account-card=nearest-pair'
)
