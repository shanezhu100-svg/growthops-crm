from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "const isCredentialSummaryContext=()=>isAccountAssetPage()||vm.currentPage==='client-detail'",
    "if(!isCredentialSummaryContext()||!accountSafeSummaryData)return;",
    "if(!isCredentialSummaryContext())",
    "vm.currentUser?.role!=='ADMIN'||!isCredentialSummaryContext()||!accountSafeSummaryData",
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "p_field:field",
    '登录账号 / 邮箱已显示；密码 / 2FA 请点击对应眼睛并验证管理员身份',
):
    require(marker in security,f'client-detail credential marker missing: {marker}')

require('revealSelectedClientLegacy' not in security,'legacy full-client reveal wrapper must be removed from final frontend')
for forbidden in (
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    'flattenSecretFields(bundle',
):
    require(forbidden not in security,f'client-detail broader reveal path survived: {forbidden}')
require("cloud.rpc('crm_reveal_client_secret_value_v5'" in security,
        'client-detail must use v5 single-value reveal')
require("setTimeout(hide,10000)" in security,'password / 2FA must still auto-hide after 10 seconds')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';" in security,'protected password eye missing')
require("if(document.hidden){clearReveal();clearCredentialUnlock();}" in security,'hidden-tab secret cleanup missing')

print('CREDENTIAL_CLIENT_DETAIL_V4_OUTPUT_TESTS_OK: reveal_transport=v5-single-value; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
