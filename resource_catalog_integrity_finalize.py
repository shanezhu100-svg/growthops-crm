from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RESOURCE_CATALOG_INTEGRITY_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    signature = re.compile(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', re.M)
    match = signature.search(text)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    tail = text[start:]
    defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
    if len(defs) < 2 or defs[0].group(1) != name:
        fail(f'{name} boundary parser drifted')
    end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
    return start, end


def replace_method(text: str, name: str, patcher):
    bounds = method_bounds(text, name)
    if bounds is None:
        return text, False
    start, end = bounds
    source = text[start:end]
    patched = patcher(source)
    if patched == source:
        fail(f'{name} patch made no change')
    return text[:start] + patched + text[end:], True


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')


def patch_save_external(source: str) -> str:
    old = "if(isEdit){const i=client[key].findIndex(a=>String(a.id)===String(f.id));if(i>=0)client[key][i]=f;else client[key].unshift({...f,id:this.accountUid(type==='GOOGLE'?'google':'ig')})}else client[key].unshift({...f,id:this.accountUid(type==='GOOGLE'?'google':'ig')});"
    new = "if(isEdit){const i=client[key].findIndex(a=>String(a.id)===String(f.id));if(i<0){this.notify('该账号资产已不存在，请刷新页面后重试');return;}client[key][i]=f}else client[key].unshift({...f,id:this.accountUid(type==='GOOGLE'?'google':'ig')});"
    if source.count(old) != 1:
        fail(f'saveExternalAsset stale-edit anchor count={source.count(old)}')
    return source.replace(old, new, 1)


def patch_delete_external(source: str) -> str:
    head = "const isGoogle=type==='GOOGLE',key=isGoogle?'googleAccounts':'instagramAccounts',label=isGoogle?'Google':'Instagram';this.askConfirm("
    replacement = (
        "const isGoogle=type==='GOOGLE',key=isGoogle?'googleAccounts':'instagramAccounts',label=isGoogle?'Google':'Instagram';"
        "const externalAssetById=()=>((client[key]||[]).find(a=>String(a.id)===String(account.id))),currentAccount=externalAssetById();"
        "if(!currentAccount){this.notify('该账号资产已不存在，请刷新页面后重试');return;}"
        "this.askConfirm("
    )
    if source.count(head) != 1:
        fail(f'deleteExternalAsset live-target head anchor count={source.count(head)}')
    source = source.replace(head, replacement, 1)
    source = source.replace("account.accountName||label+' 账号'", "currentAccount.accountName||label+' 账号'", 1)
    callback_old = "confirmText:'确认删除'},()=>{client[key]=(client[key]||[]).filter(a=>String(a.id)!==String(account.id));this.persist();this.logAudit(`删除 ${label} 账号`,`${client.name} · ${account.accountName||''}`);"
    callback_new = (
        "confirmText:'确认删除'},()=>{const liveAccount=externalAssetById();"
        "if(!liveAccount){this.notify('该账号资产已不存在，请刷新页面后重试');return;}"
        "client[key]=(client[key]||[]).filter(a=>String(a.id)!==String(liveAccount.id));"
        "this.persist();this.logAudit(`删除 ${label} 账号`,`${client.name} · ${liveAccount.accountName||''}`);"
    )
    if source.count(callback_old) != 1:
        fail(f'deleteExternalAsset confirmation recheck anchor count={source.count(callback_old)}')
    return source.replace(callback_old, callback_new, 1)


def patch_save_media_tool(source: str) -> str:
    old = "if(payload.id){const i=this.mediaTools.findIndex(t=>t.id===payload.id);if(i>-1)this.mediaTools[i]=payload}else this.mediaTools.unshift({...payload,id:this.accountUid('tool')});this.persist();"
    new = "if(payload.id){const i=this.mediaTools.findIndex(t=>t.id===payload.id);if(i<0){this.notify('该投放工具已不存在，请刷新页面后重试');return;}this.mediaTools[i]=payload}else this.mediaTools.unshift({...payload,id:this.accountUid('tool')});this.persist();"
    if source.count(old) != 1:
        fail(f'saveMediaTool stale-edit anchor count={source.count(old)}')
    return source.replace(old, new, 1)


found = {'saveExternalAsset': 0, 'deleteExternalAsset': 0, 'saveMediaTool': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    text, did_save_external = replace_method(text, 'saveExternalAsset', patch_save_external)
    if did_save_external:
        found['saveExternalAsset'] += 1
    text, did_delete_external = replace_method(text, 'deleteExternalAsset', patch_delete_external)
    if did_delete_external:
        found['deleteExternalAsset'] += 1
    text, did_save_tool = replace_method(text, 'saveMediaTool', patch_save_media_tool)
    if did_save_tool:
        found['saveMediaTool'] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'RESOURCE_CATALOG_INTEGRITY_FINALIZE_OK: '
    'external-asset-edit=existing-id-required; '
    'external-asset-delete=live-target-before-confirm+rechecked-on-confirm; '
    'media-tool-edit=existing-id-required; '
    'stale=denied-before-insert+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
