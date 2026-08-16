from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')
sql=(root/'supabase/migrations/20260816_client_account_safe_summary.sql').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

start=html.find('Google 资产')
instagram=html.find('Instagram 资产',start+1)
end=html.find('<div class="flex justify-end">',instagram+1)
require(min(start,instagram,end)>=0,'Google/Instagram asset region missing')
region=html[start:end]

require("credentialsVisible ? (account.loginAccount" not in region,'Google/Instagram login identifiers must not come from ordinary Vue secret state')
require("credentialsVisible ? (account.loginPassword" not in region,'Google/Instagram passwords must never be directly rendered from ordinary Vue state')
require(region.count('读取中…')>=4,'Google/Instagram login/password cells must use neutral initial placeholders')
require(region.count('font-mono text-sm font-semibold leading-5')>=10,'Google/Instagram account value typography must remain normalized')

for marker in (
    "const LOGIN_IDENTIFIER_ATTR='data-growthops-login-identifier'",
    "crm_client_account_safe_summary",
    "ensureAccountSafeSummary",
    "applyAccountSafeSummaryToCards",
    "accountSafeSummaryData",
    "accountSafeSummaryFetchedAt",
    "platform==='google'",
    "platform==='instagram'",
    "'登录邮箱'",
    "'登录邮箱 / 手机号'",
    "row.accountCell.textContent=login||'未录入'",
    "row.passwordCell.textContent=recorded?'••••••••':'未录入'",
    "if(!['facebook','tiktok'].includes(row.platform))continue;",
    "applyAccountSafeSummaryToCards();",
):
    require(marker in security,f'account login identifier UI marker missing: {marker}')

require("sessionStorage.setItem" not in security[security.find('const ensureAccountSafeSummary'):security.find('const applyCredentialLoadingToCards')],
        'login identifiers must not be persisted to sessionStorage')
require("setTimeout(hide,10000)" in security,'password / 2FA field reveal must still auto-hide after 10 seconds')
require("setTimeout(clearReveal,30000)" in security,'full Vault reveal must still clear after 30 seconds')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye\"></i>';" in security,'password reveal must retain the eye icon')
require("toggle.innerHTML='<i class=\"fa-regular fa-eye-slash\"></i>';" in security,'password hide control must retain the eye-slash icon')

for marker in (
    'create or replace function public.crm_client_account_safe_summary',
    "c.role not in ('ADMIN','OPS')",
    'crm_read_workspace_secrets',
    "'loginAccount'",
    "'hasPassword'",
    "'has2FA'",
    "v_client->>'fbLoginAccount'",
    "v_client->>'tkLoginAccount'",
    "v_client->'googleAccounts'",
    "v_client->'instagramAccounts'",
    'revoke all on function public.crm_client_account_safe_summary(text,text) from public',
):
    require(marker in sql,f'safe account summary SQL marker missing: {marker}')

# The safe summary may inspect password fields only to calculate booleans. It must not
# expose password / 2FA values as response keys.
require("'loginPassword'," not in sql and "'password'," not in sql and "'2FA'," not in sql,
        'safe account summary must not return password / 2FA values')

print('ACCOUNT_LOGIN_IDENTIFIER_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest()+'; security='+hashlib.sha256((root/'dist'/'cloud-security-hotfix.js').read_bytes()).hexdigest())
