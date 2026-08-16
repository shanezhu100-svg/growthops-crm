from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

start=html.find('Facebook 资产')
if start<0:
    raise SystemExit('Account asset template anchor missing')
region=html[start:min(len(html),start+70000)]

loading_targets=0
false_unrecorded=0
for label in ('登录账号','密码 / 2FA'):
    pos=0
    while True:
        pos=region.find(label,pos)
        if pos<0:
            break
        window=region[pos+len(label):min(len(region),pos+1500)]
        if '读取中…' in window:
            loading_targets+=1
        if '未录入' in window and ('读取中…' not in window or window.find('未录入')<window.find('读取中…')):
            false_unrecorded+=1
        pos+=len(label)

if loading_targets!=4:
    raise SystemExit(f'Neutral credential loading defaults missing: {loading_targets}')
if false_unrecorded:
    raise SystemExit(f'False initial unrecorded credential defaults remain: {false_unrecorded}')

print('CREDENTIAL_TEMPLATE_INITIAL_OUTPUT_TESTS_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
