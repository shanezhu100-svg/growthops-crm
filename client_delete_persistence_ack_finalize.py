from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('CLIENT_DELETE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistClientLifecycleBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistClientDeleteBarrier=' in adapter:
    fail('client delete barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistClientLifecycleBarrier=()=>flushSave();',
    '  vm.persistClientLifecycleBarrier=()=>flushSave();\n  vm.persistClientDeleteBarrier=()=>flushSave();',
    'client delete barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

count = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'deleteClient')
    if bounds is None:
        continue
    count += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'this.clients=this.clients.filter',
        '(this.leads||[]).forEach',
        'growthOpsSop-${id}-',
        'this.openingDeals=this.openingDeals.filter',
        'this.financeReceivables=this.financeReceivables.filter',
        'this.financeCosts=this.financeCosts.filter',
        'this.mediaTools=this.mediaTools.map',
        'this.persist()',
        'this.logAudit(',
        'this.notify(',
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('deleteClient reviewed source drifted: ' + ', '.join(missing))
    if 'persistClientDeleteBarrier' in source:
        fail('deleteClient already contains durability barrier')
    brace = source.find('{')
    body = source[brace + 1:-1]
    wrapper = f"""deleteClient(client){{const originalAsk=this.askConfirm,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),targetId=String(client?.id??''),selectionKeys=['selectedClientId','selectedAssetsClientId','selectedSopClientId','selectedAnalyticsClientId','selectedAdsClientId'];this.askConfirm=(config,action)=>originalAsk.call(this,config,()=>{{const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;const captureRemoved=(name,predicate)=>{{const rows=Array.isArray(this[name])?this[name]:[];return rows.map((row,index)=>({{row,index,snapshot:clone(row)}})).filter(spec=>predicate(spec.row))}},removed={{clients:captureRemoved('clients',row=>String(row?.id??'')===targetId),openingDeals:captureRemoved('openingDeals',row=>String(row?.clientId??'')===targetId),financeReceivables:captureRemoved('financeReceivables',row=>String(row?.clientId??'')===targetId),financeCosts:captureRemoved('financeCosts',row=>String(row?.clientId??'')===targetId),standaloneAlerts:captureRemoved('standaloneAlerts',row=>String(row?.clientId??'')===targetId),dismissedAlerts:captureRemoved('dismissedAlerts',row=>String(row?.clientId??'')===targetId)}};const leadBefore=(Array.isArray(this.leads)?this.leads:[]).filter(row=>String(row?.convertedClientId??'')===targetId).map(row=>({{row,id:String(row?.id??''),before:clone(row)}}));const toolBefore=(Array.isArray(this.mediaTools)?this.mediaTools:[]).map((row,index)=>({{row,index,id:String(row?.id??''),removed:(Array.isArray(row?.bindings)?row.bindings:[]).map((binding,bindingIndex)=>({{binding,bindingIndex}})).filter(spec=>String(spec.binding?.clientId??'')===targetId)}})).filter(spec=>spec.removed.length);const selectionBefore=Object.fromEntries(selectionKeys.map(key=>[key,clone(this[key])]));const sopBefore=[];try{{for(let i=0;i<localStorage.length;i++){{const key=localStorage.key(i);if(key&&(key.startsWith(`growthOpsSop-${{targetId}}-`)||key.startsWith(`sop-${{targetId}}-`)))sopBefore.push([key,localStorage.getItem(key)])}}}}catch(e){{}}let persistCalls=0;const notices=[],attemptAudits=[];this.persist=()=>{{persistCalls+=1;return true}};this.notify=(...args)=>{{notices.push(args)}};let actionResult;try{{actionResult=action();for(const row of (Array.isArray(this.auditLogs)?this.auditLogs:[]))if(!beforeAudits.has(row))attemptAudits.push(row)}}finally{{this.persist=originalPersist;this.notify=originalNotify}}if(!persistCalls){{for(const args of notices)originalNotify.apply(this,args);return actionResult}}const leadAfter=leadBefore.map(spec=>({{...spec,after:clone(spec.row)}}));const toolAfter=toolBefore.map(spec=>({{...spec,attemptRow:(Array.isArray(this.mediaTools)?this.mediaTools:[]).find(row=>String(row?.id??'')===spec.id)||null}}));const selectionAfter=Object.fromEntries(selectionKeys.map(key=>[key,clone(this[key])]));const restoreDeleted=(name,specs,idField='id')=>{{const rows=Array.isArray(this[name])?this[name]:[];for(const spec of [...specs].sort((a,b)=>a.index-b.index)){{const id=String(spec.snapshot?.[idField]??'');if(id&&rows.some(row=>String(row?.[idField]??'')===id))continue;const at=Math.max(0,Math.min(spec.index,rows.length));rows.splice(at,0,clone(spec.snapshot))}}}};const rollback=()=>{{if(Array.isArray(this.auditLogs)&&attemptAudits.length){{const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}}restoreDeleted('clients',removed.clients);restoreDeleted('openingDeals',removed.openingDeals);restoreDeleted('financeReceivables',removed.financeReceivables);restoreDeleted('financeCosts',removed.financeCosts);restoreDeleted('standaloneAlerts',removed.standaloneAlerts);restoreDeleted('dismissedAlerts',removed.dismissedAlerts);for(const spec of leadAfter){{const current=(Array.isArray(this.leads)?this.leads:[]).find(row=>row===spec.row);if(!current)continue;const keys=new Set([...Object.keys(spec.before||{{}}),...Object.keys(spec.after||{{}})]);for(const key of keys){{const beforeValue=spec.before?.[key],afterValue=spec.after?.[key];if(same(beforeValue,afterValue))continue;if(same(current?.[key],afterValue))current[key]=clone(beforeValue)}}}}for(const spec of toolAfter){{const current=(Array.isArray(this.mediaTools)?this.mediaTools:[]).find(row=>String(row?.id??'')===spec.id)||null;if(!current||current!==spec.attemptRow)continue;const bindings=Array.isArray(current.bindings)?current.bindings:(current.bindings=[]);if(bindings.some(binding=>String(binding?.clientId??'')===targetId))continue;for(const item of [...spec.removed].sort((a,b)=>a.bindingIndex-b.bindingIndex)){{const at=Math.max(0,Math.min(item.bindingIndex,bindings.length));bindings.splice(at,0,clone(item.binding))}}}}for(const key of selectionKeys)if(same(this[key],selectionAfter[key]))this[key]=clone(selectionBefore[key]);try{{for(const [key,value] of sopBefore)if(localStorage.getItem(key)===null)localStorage.setItem(key,value)}}catch(e){{}}}};if(typeof this.persistClientDeleteBarrier!=='function'){{rollback();originalNotify.call(this,'客户永久删除未保存：云端持久化服务不可用');return}}return Promise.resolve(this.persistClientDeleteBarrier()).then(()=>{{for(const args of notices)originalNotify.apply(this,args)}},e=>{{rollback();originalPersist.call(this);originalNotify.call(this,`客户永久删除未保存：云端保存失败，已恢复原状态：${{e?.message||'保存失败'}}`)}})}});try{{const runOriginal=()=>{{{body}}};return runOriginal()}}finally{{this.askConfirm=originalAsk}}}}"""
    patched = text[:start] + wrapper + text[end:]
    path.write_text(patched, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(patched.encode('utf-8')).hexdigest()))

if count != 1:
    fail(f'deleteClient expected in exactly one app artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')
print(
    'CLIENT_DELETE_PERSISTENCE_ACK_FINALIZE_OK: '
    'permanent-delete=original-business-cascade+cloud-ack-before-success; '
    'failure=client+related-rows+lead-fields+tool-bindings+selection+SOP+attempt-audit-rollback+rollback-persisted; '
    'concurrency=same-id+lead-field+tool-object+selection+SOP-replacement-guarded; '
    'save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
