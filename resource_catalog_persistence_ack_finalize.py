from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RESOURCE_CATALOG_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    open_pos = text.find('{', start)
    if open_pos < 0:
        fail(f'{name} opening brace missing')
    depth = 0
    quote = ''
    escaped = False
    line_comment = False
    block_comment = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n': line_comment = False
            i += 1; continue
        if block_comment:
            if ch == '*' and nxt == '/': block_comment = False; i += 2; continue
            i += 1; continue
        if quote:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == quote: quote = ''
            i += 1; continue
        if ch == '/' and nxt == '/': line_comment = True; i += 2; continue
        if ch == '/' and nxt == '*': block_comment = True; i += 2; continue
        if ch in ('"', "'", '`'): quote = ch; i += 1; continue
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return start, i + 1
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistLeadLinkRepairBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistResourceCatalogBarrier=' in adapter:
    fail('resource catalog barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistLeadLinkRepairBarrier=()=>flushSave();',
    '  vm.persistLeadLinkRepairBarrier=()=>flushSave();\n  vm.persistResourceCatalogBarrier=()=>flushSave();',
    'resource catalog barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacements = {
'saveExternalAsset': r'''saveExternalAsset(){if(!this.canManageAssets()){this.notify('当前角色没有维护账号资产的权限');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),client=this.clients.find(c=>String(c.id)===String(this.selectedAssetsClientId));if(!client){this.notify('当前客户不存在');return}const clientId=String(client.id),type=this.externalAssetType==='INSTAGRAM'?'INSTAGRAM':'GOOGLE',key=type==='GOOGLE'?'googleAccounts':'instagramAccounts',label=type==='GOOGLE'?'Google':'Instagram',f={...this.defaultExternalAssetForm(type),...clone(this.externalAssetForm),accountName:String(this.externalAssetForm.accountName||'').trim(),loginAccount:String(this.externalAssetForm.loginAccount||'').trim(),note:String(this.externalAssetForm.note||'').trim()};if(!f.accountName){this.notify('请填写账号名称');return}client[key]=Array.isArray(client[key])?client[key]:[];const isEdit=!!f.id,existingIndex=isEdit?client[key].findIndex(a=>String(a.id)===String(f.id)):-1;if(isEdit&&existingIndex<0){this.notify('该账号资产已不存在，请刷新页面后重试');return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify(`${label} 账号未保存：云端持久化服务不可用`);return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=isEdit?clone(client[key][existingIndex]):null,beforeIndex=existingIndex,formSnapshot=clone(this.externalAssetForm),attemptRow=isEdit?f:{...f,id:this.accountUid(type==='GOOGLE'?'google':'ig')},attemptSnapshot=clone(attemptRow);if(isEdit)client[key][existingIndex]=attemptRow;else client[key].unshift(attemptRow);this.logAudit(isEdit?`修改 ${label} 账号`:`新增 ${label} 账号`,`${client.name} · ${f.accountName}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=(this.clients||[]).find(c=>String(c.id)===clientId);if(liveClient!==client)return;liveClient[key]=Array.isArray(liveClient[key])?liveClient[key]:[];const i=liveClient[key].findIndex(a=>String(a.id)===String(attemptRow.id));if(isEdit){if(i>=0&&liveClient[key][i]===attemptRow&&same(liveClient[key][i],attemptSnapshot))liveClient[key].splice(i,1,clone(beforeSnapshot))}else if(i>=0&&liveClient[key][i]===attemptRow&&same(liveClient[key][i],attemptSnapshot))liveClient[key].splice(i,1)};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{if(this.showExternalAssetModal===true&&same(this.externalAssetForm,formSnapshot))this.showExternalAssetModal=false;this.notify(`${label} 账号已保存`)},e=>{rollback();this.persist();this.notify(`${label} 账号未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'deleteExternalAsset': r'''deleteExternalAsset(type,account){if(!this.canManageAssets()){this.notify('当前角色没有维护账号资产的权限');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),client=this.clients.find(c=>String(c.id)===String(this.selectedAssetsClientId));if(!client||!account)return;const clientId=String(client.id),isGoogle=type==='GOOGLE',key=isGoogle?'googleAccounts':'instagramAccounts',label=isGoogle?'Google':'Instagram',externalAssetById=()=>((client[key]||[]).find(a=>String(a.id)===String(account.id))),currentAccount=externalAssetById();if(!currentAccount){this.notify('该账号资产已不存在，请刷新页面后重试');return}this.askConfirm({title:`删除 ${label} 账号`,message:`确定删除【${currentAccount.accountName||label+' 账号'}】吗？\n该操作只删除当前客户的这条 ${label} 账号资产；不影响 Facebook / TikTok 及其他客户资产。`,confirmText:'确认删除'},()=>{const liveAccount=externalAssetById();if(!liveAccount){this.notify('该账号资产已不存在，请刷新页面后重试');return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify(`${label} 账号未删除：云端持久化服务不可用`);return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveAccount),beforeIndex=(client[key]||[]).indexOf(liveAccount),targetId=String(liveAccount.id);client[key]=(client[key]||[]).filter(a=>String(a.id)!==targetId);this.logAudit(`删除 ${label} 账号`,`${client.name} · ${liveAccount.accountName||''}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=(this.clients||[]).find(c=>String(c.id)===clientId);if(liveClient!==client)return;liveClient[key]=Array.isArray(liveClient[key])?liveClient[key]:[];if(liveClient[key].some(a=>String(a.id)===targetId))return;const at=Math.max(0,Math.min(beforeIndex,liveClient[key].length));liveClient[key].splice(at,0,clone(beforeSnapshot))};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{this.notify(`${label} 账号已删除`)},e=>{rollback();this.persist();this.notify(`${label} 账号未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
'saveMediaTool': r'''saveMediaTool(){if(!this.toolForm.name)return;if(!(this.toolForm.bindings||[]).length){this.notify('请至少绑定一个客户或客户账号');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),payload=this.normalizeMediaTool({...this.toolForm,loginPassword:this.toolForm.loginPassword||'',seats:Number(this.toolForm.seats||1)}),isEdit=!!payload.id,existingIndex=isEdit?this.mediaTools.findIndex(t=>t.id===payload.id):-1;if(isEdit&&existingIndex<0){this.notify('该投放工具已不存在，请刷新页面后重试');return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify('投放工具未保存：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=isEdit?clone(this.mediaTools[existingIndex]):null,beforeIndex=existingIndex,formSnapshot=clone(this.toolForm),attemptRow=isEdit?payload:{...payload,id:this.accountUid('tool')},attemptSnapshot=clone(attemptRow);if(isEdit)this.mediaTools[existingIndex]=attemptRow;else this.mediaTools.unshift(attemptRow);this.logAudit(isEdit?'修改投放工具':'新增投放工具',`${payload.name} · ${(payload.bindings||[]).length} 个绑定范围`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),targetId=String(attemptRow.id),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const i=(this.mediaTools||[]).findIndex(t=>String(t.id)===targetId);if(isEdit){if(i>=0&&this.mediaTools[i]===attemptRow&&same(this.mediaTools[i],attemptSnapshot))this.mediaTools.splice(i,1,clone(beforeSnapshot))}else if(i>=0&&this.mediaTools[i]===attemptRow&&same(this.mediaTools[i],attemptSnapshot))this.mediaTools.splice(i,1)};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{if(this.showToolModal===true&&same(this.toolForm,formSnapshot))this.showToolModal=false;this.notify('投放工具已保存')},e=>{rollback();this.persist();this.notify(`投放工具未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'deleteMediaTool': r'''deleteMediaTool(tool){if(!tool)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),mediaToolById=()=>((this.mediaTools||[]).find(t=>String(t.id)===String(tool.id))),currentTool=mediaToolById();if(!currentTool){this.notify('该投放工具已不存在，请刷新页面后重试');return}const bindingCount=(currentTool.bindings||[]).length;this.askConfirm({title:'删除投放工具',message:`确定删除投放工具【${tool.name}】吗？\n该工具当前绑定 ${bindingCount} 个客户/账号范围，删除后这些绑定会同步移除。`,confirmText:'确认删除'},()=>{const liveTool=mediaToolById();if(!liveTool){this.notify('该投放工具已不存在，请刷新页面后重试');return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify('投放工具未删除：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveTool),beforeIndex=(this.mediaTools||[]).indexOf(liveTool),targetId=String(liveTool.id),hadVisible=Object.prototype.hasOwnProperty.call(this.toolPasswordVisible||{},liveTool.id),visibleValue=hadVisible?this.toolPasswordVisible[liveTool.id]:undefined;this.mediaTools=this.mediaTools.filter(t=>String(t.id)!==targetId);if(this.toolPasswordVisible)delete this.toolPasswordVisible[liveTool.id];this.logAudit('删除投放工具',liveTool.name);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(!(this.mediaTools||[]).some(t=>String(t.id)===targetId)){const at=Math.max(0,Math.min(beforeIndex,this.mediaTools.length));this.mediaTools.splice(at,0,clone(beforeSnapshot))}if(hadVisible&&this.toolPasswordVisible&&!Object.prototype.hasOwnProperty.call(this.toolPasswordVisible,liveTool.id))this.toolPasswordVisible[liveTool.id]=visibleValue};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{this.notify(`投放工具【${tool.name}】已删除`)},e=>{rollback();this.persist();this.notify(`投放工具未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
'saveReminderType': r'''saveReminderType(){if(!this.canManageReminderTypes()){this.notify('当前角色没有管理提醒类型的权限');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),name=String(this.reminderTypeForm.name||'').trim();if(!name){this.notify('请输入提醒类型名称');return}const duplicate=(this.reminderTypes||[]).find(t=>t.name===name&&String(t.key)!==String(this.reminderTypeForm.key||''));if(duplicate){this.notify('提醒类型名称已存在');return}const isEdit=!!this.reminderTypeForm.key,existing=isEdit?this.reminderTypes.find(x=>String(x.key)===String(this.reminderTypeForm.key)):null;if(isEdit&&!existing){this.notify('提醒类型不存在');return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify('提醒类型未保存：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),formSnapshot=clone(this.reminderTypeForm),beforeNewTypeKey=clone(this.newAlertForm?.typeKey),oldName=isEdit?existing.name:null,attemptType=isEdit?existing:{key:`CUSTOM_${Date.now()}`,name,system:false},attemptIndex=isEdit?this.reminderTypes.indexOf(existing):this.reminderTypes.length;if(isEdit)existing.name=name;else this.reminderTypes.push(attemptType);this.logAudit(isEdit?'修改提醒类型':'新增提醒类型',isEdit?`${oldName} → ${name}`:name);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),targetKey=String(attemptType.key),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const live=(this.reminderTypes||[]).find(t=>String(t.key)===targetKey);if(isEdit){if(live===attemptType&&live.name===name)live.name=oldName}else if(live===attemptType&&live.name===name&&live.system===false)this.reminderTypes.splice(this.reminderTypes.indexOf(live),1)};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{if(!isEdit&&this.newAlertForm&&this.newAlertForm.typeKey===beforeNewTypeKey)this.newAlertForm.typeKey=attemptType.key;if(same(this.reminderTypeForm,formSnapshot))this.resetReminderTypeForm();this.notify(isEdit?'提醒类型已修改':'提醒类型已添加')},e=>{rollback();this.persist();this.notify(`提醒类型未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'deleteReminderType': r'''deleteReminderType(type){if(!this.canManageReminderTypes()){this.notify('当前角色没有管理提醒类型的权限');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),reminderTypeByKey=()=>((this.reminderTypes||[]).find(t=>String(t.key)===String(type?.key))),currentType=reminderTypeByKey();if(!currentType){this.notify('提醒类型不存在，请刷新页面后重试');return}if(currentType.system){this.notify('系统提醒类型不能删除，只能修改显示名称');return}const used=this.reminderTypeUsageCount(currentType.key);if(used){this.notify(`该类型仍有 ${used} 条独立提醒正在使用，请先删除或更换这些提醒`);return}this.askConfirm({title:'删除提醒类型',message:`确定删除提醒类型【${type?.name||'未命名'}】吗？`,confirmText:'确认删除'},()=>{const liveType=reminderTypeByKey();if(!liveType){this.notify('提醒类型不存在，请刷新页面后重试');return}if(liveType.system){this.notify('系统提醒类型不能删除，只能修改显示名称');return}const liveUsed=this.reminderTypeUsageCount(liveType.key);if(liveUsed){this.notify(`该类型仍有 ${liveUsed} 条独立提醒正在使用，请先删除或更换这些提醒`);return}if(typeof this.persistResourceCatalogBarrier!=='function'){this.notify('提醒类型未删除：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveType),beforeIndex=(this.reminderTypes||[]).indexOf(liveType),targetKey=String(liveType.key),beforeNewTypeKey=clone(this.newAlertForm?.typeKey),beforeFilter=clone(this.alertTypeFilter);this.reminderTypes=this.reminderTypes.filter(t=>String(t.key)!==targetKey);this.logAudit('删除提醒类型',type.name||'');const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(!(this.reminderTypes||[]).some(t=>String(t.key)===targetKey)){const at=Math.max(0,Math.min(beforeIndex,this.reminderTypes.length));this.reminderTypes.splice(at,0,clone(beforeSnapshot))}};return Promise.resolve(this.persistResourceCatalogBarrier()).then(()=>{if(this.newAlertForm&&String(this.newAlertForm.typeKey)===targetKey&&this.newAlertForm.typeKey===beforeNewTypeKey)this.newAlertForm.typeKey='IP';if(String(this.alertTypeFilter)===targetKey&&this.alertTypeFilter===beforeFilter)this.alertTypeFilter='ALL';this.notify('提醒类型已删除')},e=>{rollback();this.persist();this.notify(`提醒类型未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
}

required = {
    'saveExternalAsset': ('canManageAssets()', "this.persist()", 'showExternalAssetModal=false', 'this.logAudit', '账号已保存'),
    'deleteExternalAsset': ('externalAssetById', "this.persist()", 'this.logAudit', '账号已删除'),
    'saveMediaTool': ('normalizeMediaTool', "this.persist()", 'showToolModal=false', 'this.logAudit', '投放工具已保存'),
    'deleteMediaTool': ('mediaToolById', "this.persist()", 'toolPasswordVisible', 'this.logAudit', '已删除'),
    'saveReminderType': ('canManageReminderTypes()', "this.persist()", 'resetReminderTypeForm', 'this.logAudit', '提醒类型已'),
    'deleteReminderType': ('reminderTypeByKey', 'reminderTypeUsageCount', "this.persist()", 'this.logAudit', '提醒类型已删除'),
}

counts = {name: 0 for name in replacements}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, replacement in replacements.items():
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        counts[name] += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        missing = [marker for marker in required[name] if marker not in source]
        if missing:
            fail(f'{name} reviewed source drifted: ' + ', '.join(missing))
        if 'persistResourceCatalogBarrier' in source:
            fail(f'{name} already contains resource durability barrier')
        text = text[:start] + replacement + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in counts.items():
    if count != 1:
        fail(f'{name} expected in exactly one app artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RESOURCE_CATALOG_PERSISTENCE_ACK_FINALIZE_OK: '
    'external-asset+media-tool+reminder-type save/delete=cloud-ack-before-success-ui; '
    'failure=operation-owned-row+audit-rollback+rollback-persisted; '
    'concurrency=same-id-replacement+field-level+ui-selection-preserved; '
    'validation+permission+confirm-time-live-usage-guards=preserved; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
