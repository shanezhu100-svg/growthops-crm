from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

checked=0
for platform_anchor in ('Facebook 资产','TikTok 资产'):
    anchor=html.find(platform_anchor)
    if anchor<0:
        raise SystemExit(f'Account asset platform anchor missing: {platform_anchor}')
    for label in ('登录账号','密码 / 2FA'):
        label_pos=html.find(label,anchor,anchor+12000)
        if label_pos<0:
            raise SystemExit(f'Credential label missing after {platform_anchor}: {label}')
        window=html[label_pos+len(label):label_pos+1500]
        loading=window.find('读取中…')
        unrecorded=window.find('未录入')
        if loading<0:
            raise SystemExit(f'Neutral loading default missing after {platform_anchor}: {label}')
        if unrecorded>=0 and unrecorded<loading:
            raise SystemExit(f'False unrecorded default precedes loading state after {platform_anchor}: {label}')
        checked+=1

if checked!=4:
    raise SystemExit(f'Primary credential template checks must equal 4, got {checked}')

print('CREDENTIAL_TEMPLATE_INITIAL_OUTPUT_TESTS_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
