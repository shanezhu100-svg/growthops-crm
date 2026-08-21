from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

start=html.find('Google 资产')
instagram=html.find('Instagram 资产', start+1)
end=html.find('<div class="flex justify-end">', instagram+1)
if min(start,instagram,end)<0:
    raise SystemExit('Unable to bound Google/Instagram asset template region')
region=html[start:end]

platform_specific=(
    ('<div class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Google 账号 ${clampedAssetPagerIndex(\'assets\',\'GOOGLE\',(selectedAssetsClient.googleAccounts||[]).length)+1}` }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Google 账号 ${clampedAssetPagerIndex(\'assets\',\'GOOGLE\',(selectedAssetsClient.googleAccounts||[]).length)+1}` }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.customerId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.customerId || \'未录入\' }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.mccId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.mccId || \'未录入\' }}</div>'),
    ('<div class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Instagram 账号 ${clampedAssetPagerIndex(\'assets\',\'INSTAGRAM\',(selectedAssetsClient.instagramAccounts||[]).length)+1}` }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Instagram 账号 ${clampedAssetPagerIndex(\'assets\',\'INSTAGRAM\',(selectedAssetsClient.instagramAccounts||[]).length)+1}` }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.username || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.username || \'未录入\' }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.profileId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.profileId || \'未录入\' }}</div>'),
)
shared=(
    ('<div class="font-mono text-xs mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>', 2),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>', 2),
)

for old,new in platform_specific:
    count=region.count(old)
    if count!=1:
        raise SystemExit(f'Unexpected platform-specific typography target count: {count} :: {old[:100]}')
    region=region.replace(old,new,1)

for old,new,expected in shared:
    count=region.count(old)
    if count!=expected:
        raise SystemExit(f'Unexpected shared credential typography target count: {count} != {expected}')
    region=region.replace(old,new,expected)

html=html[:start]+region+html[end:]
index_path.write_text(html,encoding='utf-8')
print('ACCOUNT_ASSET_VALUE_TYPOGRAPHY_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
