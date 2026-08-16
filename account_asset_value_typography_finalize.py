from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

replacements=(
    # Google
    ('<div class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Google 账号 ${clampedAssetPagerIndex(\'assets\',\'GOOGLE\',(selectedAssetsClient.googleAccounts||[]).length)+1}` }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Google 账号 ${clampedAssetPagerIndex(\'assets\',\'GOOGLE\',(selectedAssetsClient.googleAccounts||[]).length)+1}` }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.customerId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.customerId || \'未录入\' }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.mccId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.mccId || \'未录入\' }}</div>'),
    ('<div class="font-mono text-xs mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>'),
    # Instagram
    ('<div class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Instagram 账号 ${clampedAssetPagerIndex(\'assets\',\'INSTAGRAM\',(selectedAssetsClient.instagramAccounts||[]).length)+1}` }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Instagram 账号 ${clampedAssetPagerIndex(\'assets\',\'INSTAGRAM\',(selectedAssetsClient.instagramAccounts||[]).length)+1}` }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.username || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.username || \'未录入\' }}</div>'),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ account.profileId || \'未录入\' }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.profileId || \'未录入\' }}</div>'),
)

# The Google and Instagram login/password templates share the same expressions/classes,
# so those two replacements must occur exactly twice (once per platform).
shared_replacements=(
    ('<div class="font-mono text-xs mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\') : (account.loginAccount ? maskAccount(account.loginAccount) : \'未录入\') }}</div>', 2),
    ('<div class="font-mono text-xs font-bold mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>',
     '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\') : (account.loginPassword ? \'••••••••••••\' : \'未录入\') }}</div>', 2),
)

# Apply platform-specific rows first, excluding shared credential rows.
platform_specific=(replacements[0],replacements[1],replacements[2],replacements[5],replacements[6],replacements[7])
for old,new in platform_specific:
    count=html.count(old)
    if count!=1:
        raise SystemExit(f'Unexpected account asset typography target count: {count} :: {old[:90]}')
    html=html.replace(old,new,1)

for old,new,expected in shared_replacements:
    count=html.count(old)
    if count!=expected:
        raise SystemExit(f'Unexpected shared credential typography target count: {count} != {expected}')
    html=html.replace(old,new,expected)

index_path.write_text(html,encoding='utf-8')
print('ACCOUNT_ASSET_VALUE_TYPOGRAPHY_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
