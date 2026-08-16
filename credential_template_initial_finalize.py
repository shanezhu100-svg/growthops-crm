from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

def target_fallback(platform_anchor,label):
    anchor=html.find(platform_anchor)
    if anchor<0:
        raise SystemExit(f'Account asset platform anchor missing: {platform_anchor}')
    label_pos=html.find(label,anchor,anchor+12000)
    if label_pos<0:
        raise SystemExit(f'Credential label missing after {platform_anchor}: {label}')
    fallback=html.find('未录入',label_pos+len(label),label_pos+1500)
    if fallback<0:
        raise SystemExit(f'Credential initial fallback missing after {platform_anchor}: {label}')
    return fallback

targets=[]
for platform_anchor in ('Facebook 资产','TikTok 资产'):
    for label in ('登录账号','密码 / 2FA'):
        targets.append(target_fallback(platform_anchor,label))

targets=sorted(set(targets))
if len(targets)!=4:
    raise SystemExit(f'Primary credential fallback targets must be exactly 4, got {len(targets)}')

for pos in reversed(targets):
    html=html[:pos]+'读取中…'+html[pos+len('未录入'):]

index_path.write_text(html,encoding='utf-8')
print('CREDENTIAL_TEMPLATE_INITIAL_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
