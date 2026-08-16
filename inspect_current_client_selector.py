from pathlib import Path

html=(Path(__file__).resolve().parent/'dist'/'index.html').read_text(encoding='utf-8')
needle='当前客户'
pos=0
found=0
while True:
    idx=html.find(needle,pos)
    if idx<0: break
    found+=1
    start=max(0,idx-1800)
    end=min(len(html),idx+4200)
    print(f'=== CURRENT_CLIENT_SELECTOR_{found} at {idx} ===')
    print(html[start:end])
    pos=idx+len(needle)
print('CURRENT_CLIENT_SELECTOR_COUNT',found)

for needle2 in ('selectedAssetClientId','assetClientId','clientAssetClientId','currentClient'):
    pos=0
    n=0
    while True:
        idx=html.find(needle2,pos)
        if idx<0: break
        n+=1
        print(f'=== {needle2}_{n} at {idx} ===')
        print(html[max(0,idx-700):min(len(html),idx+1400)])
        pos=idx+len(needle2)
    print(needle2,'COUNT',n)
