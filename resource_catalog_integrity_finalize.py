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


def patch_delete_media_tool(source: str) -> str:
    head = "if(!tool)return;const bindingCount=(tool.bindings||[]).length;this.askConfirm("
    replacement = (
        "if(!tool)return;"
        "const mediaToolById=()=>((this.mediaTools||[]).find(t=>String(t.id)===String(tool.id))),currentTool=mediaToolById();"
        "if(!currentTool){this.notify('该投放工具已不存在，请刷新页面后重试');return;}"
        "const bindingCount=(currentTool.bindings||[]).length;this.askConfirm("
    )
    if source.count(head) != 1:
        fail(f'deleteMediaTool live-target head anchor count={source.count(head)}')
    source = source.replace(head, replacement, 1)

    delete_pattern = re.compile(r"this\.mediaTools\s*=\s*this\.mediaTools\.filter\(t\s*=>\s*[^;]+\);")
    matches = list(delete_pattern.finditer(source))
    if len(matches) != 1:
        fail(f'deleteMediaTool delete assignment count={len(matches)}')
    delete_new = (
        "const liveTool=mediaToolById();"
        "if(!liveTool){this.notify('该投放工具已不存在，请刷新页面后重试');return;}"
        "this.mediaTools=this.mediaTools.filter(t=>String(t.id)!==String(liveTool.id));"
    )
    source = delete_pattern.sub(delete_new, source, count=1)

    password_pattern = re.compile(r"delete\s+this\.toolPasswordVisible\[[^\]]+\];")
    password_matches = list(password_pattern.finditer(source))
    if len(password_matches) != 1:
        fail(f'deleteMediaTool password cleanup count={len(password_matches)}')
    source = password_pattern.sub("delete this.toolPasswordVisible[liveTool.id];", source, count=1)

    audit_pattern = re.compile(r"this\.logAudit\('删除投放工具'\s*,\s*[^)]+\);")
    audit_matches = list(audit_pattern.finditer(source))
    if len(audit_matches) != 1:
        fail(f'deleteMediaTool audit count={len(audit_matches)}')
    source = audit_pattern.sub("this.logAudit('删除投放工具',liveTool.name);", source, count=1)
    return source


def patch_delete_reminder_type(source: str) -> str:
    identity_old = "if(type?.system){this.notify('系统提醒类型不能删除，只能修改显示名称');return}const used=this.reminderTypeUsageCount(type?.key);"
    identity_new = (
        "const reminderTypeByKey=()=>((this.reminderTypes||[]).find(t=>String(t.key)===String(type?.key))),currentType=reminderTypeByKey();"
        "if(!currentType){this.notify('提醒类型不存在，请刷新页面后重试');return;}"
        "if(currentType.system){this.notify('系统提醒类型不能删除，只能修改显示名称');return}"
        "const used=this.reminderTypeUsageCount(currentType.key);"
    )
    if source.count(identity_old) != 1:
        fail(f'deleteReminderType live-target anchor count={source.count(identity_old)}')
    source = source.replace(identity_old, identity_new, 1)

    delete_pattern = re.compile(r"this\.reminderTypes\s*=\s*this\.reminderTypes\.filter\(t\s*=>\s*[^;]+\);")
    matches = list(delete_pattern.finditer(source))
    if len(matches) != 1:
        fail(f'deleteReminderType delete assignment count={len(matches)}')
    delete_new = (
        "const liveType=reminderTypeByKey();"
        "if(!liveType){this.notify('提醒类型不存在，请刷新页面后重试');return;}"
        "if(liveType.system){this.notify('系统提醒类型不能删除，只能修改显示名称');return;}"
        "const liveUsed=this.reminderTypeUsageCount(liveType.key);"
        "if(liveUsed){this.notify(`该类型仍有 ${liveUsed} 条独立提醒正在使用，请先删除或更换这些提醒`);return;}"
        "this.reminderTypes=this.reminderTypes.filter(t=>String(t.key)!==String(liveType.key));"
    )
    return delete_pattern.sub(delete_new, source, count=1)


found = {
    'saveExternalAsset': 0,
    'deleteExternalAsset': 0,
    'saveMediaTool': 0,
    'deleteMediaTool': 0,
    'deleteReminderType': 0,
}
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
    text, did_delete_tool = replace_method(text, 'deleteMediaTool', patch_delete_media_tool)
    if did_delete_tool:
        found['deleteMediaTool'] += 1
    text, did_delete_reminder_type = replace_method(text, 'deleteReminderType', patch_delete_reminder_type)
    if did_delete_reminder_type:
        found['deleteReminderType'] += 1
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
    'media-tool-delete=live-target-before-confirm+rechecked-on-confirm; '
    'reminder-type-save=existing-canonical-stale-edit-guard; '
    'reminder-type-delete=live-target+usage-before-confirm+rechecked-on-confirm; '
    'stale=denied-before-mutation+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
