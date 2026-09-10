from pathlib import Path

ROOT = Path(__file__).resolve().parent
html_path = ROOT / 'dist' / 'index.html'
app_dir = ROOT / 'dist' / 'app'

if html_path.is_file():
    text = html_path.read_text(encoding='utf-8')
    for marker in ('monthlyFee', 'billingMode', '月服务费', '计费'):
        idx = text.find(marker)
        if idx >= 0:
            snippet = text[max(0, idx-500):idx+1200].replace('\n',' ')
            print(f'COLLECTION_PLAN_UI_HTML_PROBE[{marker}]: {snippet}')
for path in sorted(app_dir.glob('app-inline-*.js')):
    text = path.read_text(encoding='utf-8')
    for marker in ('defaultClientForm', 'monthlyFee', 'billingMode'):
        idx = text.find(marker)
        if idx >= 0:
            snippet = text[max(0, idx-500):idx+1400].replace('\n',' ')
            print(f'COLLECTION_PLAN_UI_JS_PROBE[{path.name}:{marker}]: {snippet}')
