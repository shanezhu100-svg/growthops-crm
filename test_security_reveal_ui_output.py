from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    '平台资产与账号',
    'id="growthops-secure-credential-button"',
    "v-if=\"currentUser?.role==='ADMIN'\"",
    'v-else-if="canViewCredentials()"',
    '密码 / 2FA 需单独显示，30 秒后自动清除',
    '查看登录资料',
):
    require(marker in html,f'unified inline login credential control missing: {marker}')

require(html.count('id="growthops-secure-credential-button"')==1,'secure login reveal button must exist exactly once in Vue template')
require('安全查看客户凭证' not in html,'separate secure credential button must remain removed from client detail header')
require('@click="credentialsVisible=!credentialsVisible"' in html,'non-ADMIN credential visibility behavior must remain available to existing permitted roles')
require('position:fixed;right:18px;bottom:72px' not in security,'legacy floating reveal button remains')
require('document.body.appendChild(button)' not in security,'security script must not append reveal control into Vue-owned DOM')
# The consolidated reveal stage runs after admin-unlock hardening, so one overlay is
# expected for the short-lived administrator password challenge. It must be the
# unlock prompt, not a legacy secret-display modal.
require(security.count('document.body.appendChild(overlay)')==1,'only the administrator unlock overlay may be attached')
require('验证管理员身份' in security and '验证并解锁' in security,'administrator unlock overlay markers missing')
require('button.remove()' not in security,'security script must not remove Vue-owned reveal control')
require('host.header.appendChild(button)' not in security,'security script must not mutate client-detail child structure')
require("crm_reveal_client_secrets" in security,'legacy full reveal definition missing before final v6 cleanup')
require('setTimeout(clearReveal,30000)' in security,'30-second Vault memory lifetime missing')
require('setTimeout(hide,10000)' in security,'per-field 10-second clear missing')
require('navigator.clipboard' not in security,'secure reveal must not auto-copy credentials')

for marker in (
    "const INLINE_ATTR='data-growthops-vault-inline'",
    'setRevealButtonState','隐藏登录资料','locateCredentialRows','credentialCardForLabel','valueCellForLabel',
    'platformForCard','scoreSecretField','bestSecretValue','applyInlineSecrets','setInlineValue','setInlineSecretControl',
    'prepareInlineCell',"exactLeaf(card,'登录账号')","exactLeaf(card,'密码 / 2FA')",
    "data-growthops-vault-kind",'Vault 已加载 · 点击眼睛显示 10 秒',
    'isAccountAssetPage','accountAssetRevealButtons','secureRevealButtons','resolveCredentialClientId',
    "bodyText.includes('Facebook 资产')","bodyText.includes('TikTok 资产')",
    "['selectedClientId','selectedAssetClientId','assetClientId','clientAssetClientId']",
    "window.addEventListener('blur',clearReveal)","window.addEventListener('pagehide',clearReveal)",
    'CREDENTIAL_REAUTH_REQUIRED','CREDENTIAL_REVEAL_THROTTLED'
):
    require(marker in security,f'inline Vault reveal marker missing: {marker}')

require("const inCredentialContext=vm.currentPage==='client-detail'||isAccountAssetPage();" in security,'Vault reveal must support both client detail and account asset views')
require("const visible=vm.currentUser?.role==='ADMIN'&&inCredentialContext&&clientId!=='';" in security,'Vault reveal must remain ADMIN-only and require a resolved client')
require("const label=cleanText(button);" in security and "label==='查看登录资料'||label==='隐藏登录资料'" in security,'existing account asset login-details button must be adopted')
require("button.addEventListener('click',event=>" in security and "event.stopImmediatePropagation();" in security and "},true);" in security,'secure handler must intercept the legacy asset-page visibility toggle')
require("const clientId=resolveCredentialClientId();" in security,'Vault RPC must resolve the active client on account asset pages')
require("if(revealData){clearReveal();return;}" in security,'clicking the unified control while loaded must clear credentials without another Vault fetch')
require('if(revealData)clearReveal();' in security,'inline reveal must clear when leaving an authorized credential context')

require("if(value.includes('facebook'))return 'facebook';" in security,'Facebook credential cards must be detected independently')
require("if(value.includes('tiktok'))return 'tiktok';" in security,'TikTok credential cards must be detected independently')
require("if(platform==='facebook')" in security and "if(key.includes('fblogin'))score+=45;" in security,'Facebook Vault fields must be platform-scored')
require("else if(platform==='tiktok')" in security and "if(key.includes('tklogin'))score+=45;" in security,'TikTok Vault fields must be platform-scored')
require("cell.dataset.growthopsVaultPrevious=cell.textContent||'';" in security,'inline reveal must preserve the previous masked or not-entered value')
require("cell.textContent=value;" in security,'login account may render into the existing value cell')
require("display.textContent='••••••••';" in security,'password / 2FA must remain masked after Vault load')
require("display.textContent=value;" in security,'password / 2FA may reveal only after field eye activation')
require("toggle.setAttribute('aria-label','显示密码和 2FA')" in security,'secret eye control must be accessible')
require("el.textContent=el.dataset.growthopsVaultPrevious;" in security,'auto-clear must restore the previous value')
require("secureParts.push(`2FA: ${twofa}`);" in security,'password / 2FA row must support 2FA inline')
require("revealData={active:true,clientId:String(clientId)};" in security,'full secret tree must not remain in the global reveal state')
require('secretTree=null;' in security,'temporary secret tree reference must be released after rendering field controls')
require('renderRevealModal(clientId,secretTree)' in security,'existing reveal call contract must remain stable until final v6 cleanup')

# Active per-field browser reads must already be least-privilege at this stage.
for forbidden in (
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    'flattenSecretFields(bundle',
):
    require(forbidden not in security,f'broader credential reveal survived consolidated stage: {forbidden}')
require("cloud.rpc('crm_reveal_client_secret_value_v5'" in security,'v5 scalar reveal transport missing')
require("cloud.rpc('crm_unlock_credentials_v1'" in security,'administrator unlock transport missing')

print('SECURITY_REVEAL_UI_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
