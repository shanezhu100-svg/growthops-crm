from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_PROVIDER_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = ''
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
            if depth < 0:
                break
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistOpeningDealBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistOpeningProviderBarrier=' in adapter:
    fail('opening provider barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistOpeningDealBarrier=()=>flushSave();',
    '  vm.persistOpeningDealBarrier=()=>flushSave();\n  vm.persistOpeningProviderBarrier=()=>flushSave();',
    'opening provider barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'saveOpeningProvider')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        '该开户商记录已不存在',
        '返点政策请输入有效生效日期',
        'this.openingProviders',
        'this.openingDeals',
        'this.persist()',
        'this.logAudit(',
        'this.showProviderModal=false',
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('saveOpeningProvider reviewed source drifted: ' + ', '.join(missing))
    if 'persistOpeningProviderBarrier' in source:
        fail('saveOpeningProvider already contains opening provider barrier')
    brace = source.find('{')
    if brace < 0 or not source.endswith('}'):
        fail('saveOpeningProvider body parser drifted')
    body = source[brace + 1:-1]
    replacement = """saveOpeningProvider(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key),initialForm=clone(this.providerForm),initialId=String(initialForm?.id??''),beforeModal=this.showProviderModal,beforeProviders=Array.isArray(this.openingProviders)?[...this.openingProviders]:[],beforeProviderIds=new Set(beforeProviders.map(row=>String(row?.id??''))),beforeProvider=initialId?beforeProviders.find(row=>String(row?.id??'')===initialId)||null:null,beforeProviderSnapshot=clone(beforeProvider),beforeProviderIndex=beforeProviders.indexOf(beforeProvider),beforeLinked=initialId?(Array.isArray(this.openingDeals)?this.openingDeals:[]).filter(row=>String(row?.providerId??'')===initialId).map(row=>({id:String(row?.id??''),row,snapshot:clone(row)})):[],beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};let originalResult;try{const runOriginal=()=>{__BODY__};originalResult=runOriginal()}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return originalResult}const attemptProvider=initialId?(this.openingProviders||[]).find(row=>String(row?.id??'')===initialId)||null:(this.openingProviders||[]).find(row=>!beforeProviders.includes(row)&&!beforeProviderIds.has(String(row?.id??'')))||null,attemptId=String(attemptProvider?.id??''),attemptProviderSignature=attemptProvider?JSON.stringify(attemptProvider):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),linkedAttempts=beforeLinked.map(entry=>{const row=(Array.isArray(this.openingDeals)?this.openingDeals:[]).find(item=>String(item?.id??'')===entry.id)||null;if(!row)return null;const keys=new Set([...Object.keys(entry.snapshot||{}),...Object.keys(row||{})]),changes=[];for(const key of keys){const hadBefore=own(entry.snapshot||{},key),hadAfter=own(row||{},key),beforeValue=hadBefore?clone(entry.snapshot[key]):undefined,afterValue=hadAfter?clone(row[key]):undefined;if(hadBefore!==hadAfter||!same(beforeValue,afterValue))changes.push({key,hadBefore,hadAfter,before:beforeValue,after:afterValue})}return changes.length?{id:entry.id,row,changes}:null}).filter(Boolean),successModal=this.showProviderModal,successForm=this.providerForm;this.showProviderModal=beforeModal;this.providerForm=clone(initialForm);const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const providers=Array.isArray(this.openingProviders)?this.openingProviders:[],currentProvider=providers.find(row=>String(row?.id??'')===attemptId)||null;if(initialId){if(currentProvider===attemptProvider&&attemptProviderSignature&&JSON.stringify(currentProvider)===attemptProviderSignature&&beforeProviderSnapshot){const idx=providers.indexOf(currentProvider);if(idx>=0)providers.splice(idx,1,clone(beforeProviderSnapshot))}}else if(currentProvider===attemptProvider&&attemptProviderSignature&&JSON.stringify(currentProvider)===attemptProviderSignature){const idx=providers.indexOf(currentProvider);if(idx>=0)providers.splice(idx,1)}const deals=Array.isArray(this.openingDeals)?this.openingDeals:[];for(const entry of linkedAttempts){const current=deals.find(row=>String(row?.id??'')===entry.id)||null;if(current!==entry.row)continue;for(const change of entry.changes){const hasCurrent=own(current,change.key);if(hasCurrent!==change.hadAfter)continue;if(change.hadAfter&&!same(current[change.key],change.after))continue;if(change.hadBefore)current[change.key]=clone(change.before);else delete current[change.key]}}this.showProviderModal=beforeModal;this.providerForm=clone(initialForm)};if(typeof this.persistOpeningProviderBarrier!=='function'){rollback();originalNotify.call(this,'开户商资料未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistOpeningProviderBarrier()).then(()=>{this.showProviderModal=successModal;this.providerForm=successForm;for(const args of notices)originalNotify.apply(this,args)},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`开户商资料未保存：云端保存失败，已恢复原开户商与关联渠道状态：${e?.message||'保存失败'}`)})}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveOpeningProvider expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'OPENING_PROVIDER_PERSISTENCE_ACK_FINALIZE_OK: '
    'create+edit=original-validation+linked-deal-name-sync+cloud-ack-before-modal-success; '
    'failure=provider+linked-deal-fields+attempt-audit-rollback+rollback-persisted; '
    'concurrency=provider-identity+signature+linked-deal-object+field-compare-guarded; '
    'save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
