from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
start=html.find('Google 资产')
instagram=html.find('Instagram 资产',start+1)
end=html.find('<div class="flex justify-end">',instagram+1)
if min(start,instagram,end)<0:
    raise SystemExit('Unable to bound Google/Instagram asset template region')
region=html[start:end]

required=(
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Google 账号',
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.customerId || \'未录入\' }}</div>',
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.mccId || \'未录入\' }}</div>',
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all">{{ account.accountName || `Instagram 账号',
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.username || \'未录入\' }}</div>',
    '<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ account.profileId || \'未录入\' }}</div>',
)
for marker in required:
    if marker not in region:
        raise SystemExit(f'Account value typography marker missing: {marker[:100]}')

login_marker='<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount || \'未录入\')'
password_marker='<div class="font-mono text-sm font-semibold leading-5 mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword || \'未录入\')'
if region.count(login_marker)!=2:
    raise SystemExit(f'Google/Instagram login typography count must be 2, got {region.count(login_marker)}')
if region.count(password_marker)!=2:
    raise SystemExit(f'Google/Instagram password typography count must be 2, got {region.count(password_marker)}')

for old in (
    'class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Google 账号',
    'class="text-xs font-extrabold mt-1 break-all">{{ account.accountName || `Instagram 账号',
    'class="font-mono text-xs mt-1 break-all select-all">{{ credentialsVisible ? (account.loginAccount',
    'class="font-mono text-xs font-bold mt-1 break-all select-all">{{ credentialsVisible ? (account.loginPassword',
):
    if old in region:
        raise SystemExit(f'Old Google/Instagram typography remains: {old}')

print('ACCOUNT_ASSET_VALUE_TYPOGRAPHY_OUTPUT_TESTS_OK: index='+hashlib.sha256((root/'dist'/'index.html').read_bytes()).hexdigest())
