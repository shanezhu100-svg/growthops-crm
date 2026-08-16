from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

asset_anchor='Facebook 资产'
start=html.find(asset_anchor)
if start<0:
    raise SystemExit('Account asset template anchor not found')
# The FB/TK credential cards live together in this bounded template region.
end=min(len(html),start+70000)
region=html[start:end]

targets=[]
for label in ('登录账号','密码 / 2FA'):
    pos=0
    while True:
        pos=region.find(label,pos)
        if pos<0:
            break
        fallback=region.find('未录入',pos+len(label),min(len(region),pos+1500))
        if fallback>=0:
            targets.append(fallback)
        pos+=len(label)

# One login + one password/2FA fallback for Facebook and TikTok.
targets=sorted(set(targets))
if len(targets)!=4:
    raise SystemExit(f'Unexpected account asset credential fallback count: {len(targets)}')

for pos in reversed(targets):
    region=region[:pos]+'读取中…'+region[pos+len('未录入'):]

html=html[:start]+region+html[end:]
index_path.write_text(html,encoding='utf-8')
print('CREDENTIAL_TEMPLATE_INITIAL_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
