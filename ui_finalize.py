from pathlib import Path
import hashlib, shutil

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
adapter_path = dist / 'cloud-adapter.js'
ui_src = root / 'cloud-ui-recovery.js'
ui_dst = dist / 'cloud-ui-recovery.js'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if not ui_src.exists():
    raise SystemExit('cloud-ui-recovery.js missing')

html = index_path.read_text(encoding='utf-8')
adapter = adapter_path.read_text(encoding='utf-8')

security_tag = '<script src="/cloud-security-hotfix.js"></script>'
ui_tag = '<script src="/cloud-ui-recovery.js"></script>'
if html.count(security_tag) != 1:
    raise SystemExit('Unexpected security hotfix script tag count')
if ui_tag in html:
    raise SystemExit('UI recovery script tag already present before finalize')
html = html.replace(security_tag, security_tag + ui_tag, 1)

# Keep a serialized copy of the last confirmed cloud state. Legacy UI methods call
# persist() in many navigation and normalization paths; identical states must not
# consume a new revision or create avoidable conflict churn.
adapter = replace_once(
    adapter,
    'let suppressPersist=false;',
    'let suppressPersist=false;\n  let lastSavedStateJson=null;',
    'last saved cloud state marker'
)

adapter = replace_once(
    adapter,
    '      vm.updateStorageUsage();\n    }finally{',
    '      vm.updateStorageUsage();\n      lastSavedStateJson=JSON.stringify(payload());\n    }finally{',
    'hydrated state baseline'
)

adapter = replace_once(
    adapter,
    '    const state=payload();\n    try{const d=await rpc(\'crm_save_state\'',
    '    const state=payload();\n    const stateJson=JSON.stringify(state);\n    if(stateJson===lastSavedStateJson)return true;\n    try{const d=await rpc(\'crm_save_state\'',
    'skip unchanged cloud save'
)

adapter = replace_once(
    adapter,
    'revision=Number(d?.revision??revision+1);return true;',
    'revision=Number(d?.revision??revision+1);lastSavedStateJson=stateJson;return true;',
    'confirmed save baseline update'
)

index_path.write_text(html, encoding='utf-8')
adapter_path.write_text(adapter, encoding='utf-8')
shutil.copyfile(ui_src, ui_dst)

print(
    'UI_FINALIZE_OK: '
    f'index={sha(index_path)}; '
    f'adapter={sha(adapter_path)}; '
    f'ui={sha(ui_dst)}'
)
