from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('AD_DATA_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    m = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, flags=re.M)
    if not m:
        return None
    start = m.start() + m.group(0).index(m.group(1))
    open_pos = text.find('{', start)
    depth = 0; quote = ''; escaped = False; line_comment = False; block_comment = False; i = open_pos
    while i < len(text):
        ch = text[i]; nxt = text[i + 1] if i + 1 < len(text) else ''
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


def body_of(source: str) -> str:
    open_pos = source.find('{')
    if open_pos < 0 or not source.rstrip().endswith('}'):
        fail('method source body drifted')
    return source[open_pos + 1:source.rfind('}')]


if not ADAPTER.is_file() or 'vm.persistAdStructureBarrier=()=>flushSave();' not in ADAPTER.read_text(encoding='utf-8'):
    fail('shared ads durability barrier missing')
if not APP_DIR.is_dir():
    fail('dist/app missing')


def save_record_wrapper(source: str) -> str:
    for marker in ('adRawNumericFields', 'assertMonthUnlocked', 'syncAccountAnalyticsFromRecords', 'syncClientPlatformAnalytics', "logAudit(isUpdate?'修改广告数据':'新增广告数据'", 'this.persist()'):
        if marker not in source: fail('saveAdDataRecord reviewed source drifted: ' + marker)
    if 'persistAdStructureBarrier' in source: fail('saveAdDataRecord already ACK-aware')
    body = body_of(source)
    return "saveAdDataRecord(){const __run=()=>{" + body + "};const __clone=v=>v==null?v:JSON.parse(JSON.stringify(v)),__same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),__client=this.selectedAdsClient,__account=this.selectedAdsAccount,__platform=this.selectedAdsPlatform,__campaignId=this.adDataForm?.campaignId,__campaign=(this.savedAdsCampaignsForAccount||[]).find(c=>String(c.id)===String(__campaignId)),__analyticsKey=__platform==='FB'?'fbData':'tkData',__before={records:__clone(__account?.adDataRecords),spend:__account?.adSpend,currency:__account?.adSpendCurrency,analytics:__clone(__client?.[__analyticsKey]),campaignUpdated:__campaign?.updatedAt,modal:this.showAdDataModal,editing:this.editingAdDataRecordId},__auditBefore=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),__persist=this.persist,__notify=this.notify,__notes=[];let __writes=0;this.persist=()=>{__writes++;return true};this.notify=m=>{__notes.push(String(m))};let __result;try{__result=__run()}finally{this.persist=__persist;this.notify=__notify}if(!__writes){__notes.forEach(m=>__notify.call(this,m));return __result}const __attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(x=>!__auditBefore.has(x)),__after={records:__clone(__account?.adDataRecords),spend:__account?.adSpend,currency:__account?.adSpendCurrency,analytics:__clone(__client?.[__analyticsKey]),campaignUpdated:__campaign?.updatedAt,modal:this.showAdDataModal,editing:this.editingAdDataRecordId};if(this.showAdDataModal===__after.modal)this.showAdDataModal=__before.modal;if(this.editingAdDataRecordId===__after.editing)this.editingAdDataRecordId=__before.editing;const __rollback=()=>{if(Array.isArray(this.auditLogs)&&__attemptAudits.length){const doomed=new Set(__attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i--)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(this.selectedAdsAccount===__account){if(__same(__account.adDataRecords,__after.records))__account.adDataRecords=__clone(__before.records);if(__account.adSpend===__after.spend)__account.adSpend=__before.spend;if(__account.adSpendCurrency===__after.currency)__account.adSpendCurrency=__before.currency}if(this.selectedAdsClient===__client&&__same(__client?.[__analyticsKey],__after.analytics))__client[__analyticsKey]=__clone(__before.analytics);if(__campaign&&__campaign.updatedAt===__after.campaignUpdated)__campaign.updatedAt=__before.campaignUpdated};if(typeof this.persistAdStructureBarrier!=='function'){__rollback();__notify.call(this,'广告数据未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{if(this.showAdDataModal===__before.modal)this.showAdDataModal=__after.modal;if(this.editingAdDataRecordId===__before.editing)this.editingAdDataRecordId=__after.editing;__notes.forEach(m=>__notify.call(this,m))},e=>{__rollback();__persist.call(this);__notify.call(this,`广告数据未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}"


def delete_record_wrapper(source: str) -> str:
    for marker in ('adDeleteRecordExists', 'assertMonthUnlocked', 'syncAccountAnalyticsFromRecords', 'syncClientPlatformAnalytics', "logAudit('删除广告数据'", 'this.persist()'):
        if marker not in source: fail('deleteAdDataRecord reviewed source drifted: ' + marker)
    if 'persistAdStructureBarrier' in source: fail('deleteAdDataRecord already ACK-aware')
    body = body_of(source)
    return "deleteAdDataRecord(record){const __self=this,__ask=this.askConfirm;this.askConfirm=function(opts,cb){return __ask.call(this,opts,()=>{const __clone=v=>v==null?v:JSON.parse(JSON.stringify(v)),__same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),__client=__self.selectedAdsClient,__account=__self.selectedAdsAccount,__platform=__self.selectedAdsPlatform,__analyticsKey=__platform==='FB'?'fbData':'tkData',__before={records:__clone(__account?.adDataRecords),spend:__account?.adSpend,currency:__account?.adSpendCurrency,analytics:__clone(__client?.[__analyticsKey]),editing:__self.editingAdDataRecordId},__auditBefore=new Set(Array.isArray(__self.auditLogs)?__self.auditLogs:[]),__persist=__self.persist,__notify=__self.notify,__notes=[];let __writes=0;__self.persist=()=>{__writes++;return true};__self.notify=m=>{__notes.push(String(m))};let __r;try{__r=cb()}finally{__self.persist=__persist;__self.notify=__notify}if(!__writes){__notes.forEach(m=>__notify.call(__self,m));return __r}const __attemptAudits=(Array.isArray(__self.auditLogs)?__self.auditLogs:[]).filter(x=>!__auditBefore.has(x)),__after={records:__clone(__account?.adDataRecords),spend:__account?.adSpend,currency:__account?.adSpendCurrency,analytics:__clone(__client?.[__analyticsKey]),editing:__self.editingAdDataRecordId};if(__self.editingAdDataRecordId===__after.editing)__self.editingAdDataRecordId=__before.editing;const __rollback=()=>{if(Array.isArray(__self.auditLogs)&&__attemptAudits.length){const doomed=new Set(__attemptAudits);for(let i=__self.auditLogs.length-1;i>=0;i--)if(doomed.has(__self.auditLogs[i]))__self.auditLogs.splice(i,1)}if(__self.selectedAdsAccount===__account){if(__same(__account.adDataRecords,__after.records))__account.adDataRecords=__clone(__before.records);if(__account.adSpend===__after.spend)__account.adSpend=__before.spend;if(__account.adSpendCurrency===__after.currency)__account.adSpendCurrency=__before.currency}if(__self.selectedAdsClient===__client&&__same(__client?.[__analyticsKey],__after.analytics))__client[__analyticsKey]=__clone(__before.analytics)};if(typeof __self.persistAdStructureBarrier!=='function'){__rollback();__notify.call(__self,'广告数据未删除：云端持久化服务不可用');return}return Promise.resolve(__self.persistAdStructureBarrier()).then(()=>{if(__self.editingAdDataRecordId===__before.editing)__self.editingAdDataRecordId=__after.editing;__notes.forEach(m=>__notify.call(__self,m))},e=>{__rollback();__persist.call(__self);__notify.call(__self,`广告数据未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})};try{return (()=>{" + body + "})()}finally{this.askConfirm=__ask}}"


def save_spend_wrapper(source: str) -> str:
    for marker in ('adSpendRaw', 'adSpendValue', "this.notify('广告消耗已保存')", 'this.persist()'):
        if marker not in source: fail('saveAdSpend reviewed source drifted: ' + marker)
    if 'persistAdStructureBarrier' in source: fail('saveAdSpend already ACK-aware')
    body = body_of(source)
    return "saveAdSpend(account){if(!account)return;const __beforeSpend=account.adSpend,__beforeCurrency=account.adSpendCurrency,__persist=this.persist,__notify=this.notify,__notes=[];let __writes=0;this.persist=()=>{__writes++;return true};this.notify=m=>{__notes.push(String(m))};let __r;try{__r=(()=>{" + body + "})()}finally{this.persist=__persist;this.notify=__notify}if(!__writes){__notes.forEach(m=>__notify.call(this,m));return __r}const __afterSpend=account.adSpend,__afterCurrency=account.adSpendCurrency,__rollback=()=>{if(account.adSpend===__afterSpend)account.adSpend=__beforeSpend;if(account.adSpendCurrency===__afterCurrency)account.adSpendCurrency=__beforeCurrency};if(typeof this.persistAdStructureBarrier!=='function'){__rollback();__notify.call(this,'广告消耗未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{__notes.forEach(m=>__notify.call(this,m))},e=>{__rollback();__persist.call(this);__notify.call(this,`广告消耗未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}"

patchers = {'saveAdDataRecord': save_record_wrapper, 'deleteAdDataRecord': delete_record_wrapper, 'saveAdSpend': save_spend_wrapper}
counts = {k: 0 for k in patchers}; changed = []
for path in sorted(APP_DIR.glob('app-inline-*.js')):
    text = path.read_text(encoding='utf-8'); original = text
    for name, patcher in patchers.items():
        bounds = method_bounds(text, name)
        if bounds is None: continue
        counts[name] += 1; start, end = bounds
        text = text[:start] + patcher(text[start:end]) + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))
for name, count in counts.items():
    if count != 1: fail(f'{name} expected exactly once, found {count}')
if len(changed) != 1: fail(f'expected one changed app artifact, found {len(changed)}')
print('AD_DATA_PERSISTENCE_ACK_FINALIZE_OK: record-save+delete+account-spend=shared-cloud-ack-before-success-ui; failure=record+derived-account/client-analytics+attempt-audit-rollback+rollback-persisted; concurrency=array+field+selection-authority-preserved; original-validation+month-lock+confirm-recheck+analytics-sync=preserved; missing-barrier=fail-closed; save-queue=shared-flushSave; app=' + changed[0][0] + ':' + changed[0][1])
