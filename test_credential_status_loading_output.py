from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "credentialStatusCacheKey",
    "growthops_credential_status_v2",
    "sessionStorage.getItem",
    "sessionStorage.setItem",
    "matchCredentialValueTypography",
    "cell.style.fontFamily='ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace'",
    "cell.style.fontSize='0.875rem'",
    "cell.style.lineHeight='1.25rem'",
    "cell.style.fontWeight='600'",
    "normalizeOtherAccountAssetTypography",
    "['Google 资产',['账号名称','Google Ads 客户 ID','MCC ID','登录邮箱','密码 / 2FA']]",
    "['Instagram 资产',['账号名称','Instagram 用户名','Instagram ID','登录邮箱 / 手机号','密码 / 2FA']]",
    "assetSectionForHeading",
    "exactLeaves",
    "applyCredentialLoadingToCards",
    "cell.textContent='读取中…'",
    "cell.setAttribute(STATUS_ATTR,'loading')",
    "applyCredentialStatusUnavailable",
    "cell.textContent='状态暂不可用'",
    "matchCredentialValueTypography(row.accountCell);",
    "matchCredentialValueTypography(row.passwordCell);",
    "row.accountCell.textContent='已录入'",
    "row.passwordCell.textContent='••••••••'",
    "row.accountCell.textContent='未录入'",
    "row.passwordCell.textContent='未录入'",
    "writeCredentialStatusCache(clientId,credentialStatusData)",
    "const cached=readCredentialStatusCache(clientId);",
):
    require(marker in security,f'credential loading/cache marker missing: {marker}')

require(security.count('normalizeOtherAccountAssetTypography();')>=4,'Google/Instagram typography must refresh across initial, loading, success and error states')
require("if(cached){\n      credentialStatusData=cached.data;" in security,'refresh must render cached safe credential status immediately')
require("else{\n      credentialStatusData=null;\n      credentialStatusFetchedAt=0;\n      applyCredentialLoadingToCards();" in security,'first entry must use neutral loading state before the RPC returns')
require(".catch(()=>{\n        if(!credentialStatusData)applyCredentialStatusUnavailable();" in security,'RPC failure must not fall back to a false unrecorded state')
require("Date.now()-savedAt>300000" in security,'safe status cache must expire')
require("now-credentialStatusFetchedAt<60000" in security,'runtime credential status cache guard must remain')
require("setTimeout(hide,10000)" in security,'10-second password reveal window must remain')
require("setTimeout(clearReveal,30000)" in security,'30-second Vault reveal lifetime must remain')

print('CREDENTIAL_STATUS_LOADING_OUTPUT_TESTS_OK: security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
