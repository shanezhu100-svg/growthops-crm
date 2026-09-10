from pathlib import Path

ROOT = Path(__file__).resolve().parent
html_path = ROOT / 'dist' / 'index.html'
app_dir = ROOT / 'dist' / 'app'


def emit_all(prefix, text, marker, before=900, after=1800, limit=8):
    start = 0
    count = 0
    while count < limit:
        idx = text.find(marker, start)
        if idx < 0:
            break
        snippet = text[max(0, idx-before):idx+after].replace('\n', ' ')
        print(f'COLLECTION_PLAN_UI_{prefix}[{marker}#{count+1}@{idx}]: {snippet}')
        count += 1
        start = idx + max(1, len(marker))
    if count == 0:
        print(f'COLLECTION_PLAN_UI_{prefix}[{marker}]: NOT_FOUND')


if html_path.is_file():
    text = html_path.read_text(encoding='utf-8')
    for marker in (
        'clientForm.monthlyFee',
        'clientForm.billingMode',
        'clientForm.renewalAlertDay',
        '编辑客户',
        '新增客户',
    ):
        emit_all('HTML_PROBE', text, marker)

for path in sorted(app_dir.glob('app-inline-*.js')):
    text = path.read_text(encoding='utf-8')
    for marker in (
        'clientForm:{',
        'clientForm =',
        'clientForm=',
        'openClientForm',
        'openClientModal',
        'editClient',
        'monthlyFee:',
        'billingMode:',
    ):
        emit_all(f'JS_PROBE[{path.name}]', text, marker, before=700, after=2200)
