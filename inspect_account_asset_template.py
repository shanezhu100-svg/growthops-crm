from pathlib import Path

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
for anchor in ('Google 资产','Instagram 资产'):
    pos=html.find(anchor)
    if pos<0:
        raise SystemExit(f'anchor missing: {anchor}')
    start=max(0,pos-600)
    end=min(len(html),pos+9000)
    snippet=html[start:end]
    print(f'=== {anchor} TEMPLATE START ===')
    print(snippet)
    print(f'=== {anchor} TEMPLATE END ===')
raise SystemExit('ACCOUNT_ASSET_TEMPLATE_INSPECT_ONLY')
