from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('LEAD_SAVE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistClientSaveBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistLeadSaveBarrier=' in adapter:
    fail('lead save barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistClientSaveBarrier=()=>flushSave();',
    '  vm.persistLeadSaveBarrier=()=>flushSave();\n  vm.persistClientSaveBarrier=()=>flushSave();',
    'lead save barrier placement',
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
    bounds = method_bounds(text, 'saveLead')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = ('this.leadForm', 'this.leads', 'this.persist()', 'this.logAudit(', 'this.notify(', 'this.showLeadModal=false')
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('saveLead reviewed source drifted: ' + ', '.join(missing))
    if 'persistLeadSaveBarrier' in source:
        fail('saveLead already contains durability barrier')
    brace = source.find('{')
    if brace < 0 or not source.endswith('}'):
        fail('saveLead body parser drifted')
    body = source[brace + 1:-1]
    replacement = """saveLead(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key),beforeLeads=(Array.isArray(this.leads)?this.leads:[]).map((row,index)=>({row,index,id:String(row?.id??''),snapshot:clone(row)})),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeUi={showLeadModal:this.showLeadModal,leadPoolFilter:clone(this.leadPoolFilter),leadQuickFilter:clone(this.leadQuickFilter)},originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};let originalResult;try{const runOriginal=()=>{__BODY__};originalResult=runOriginal()}finally{this.persist=originalPersist;this.notify=originalNotify}const replayNotices=()=>{for(const args of notices)originalNotify.apply(this,args)};if(!persistCalls){replayNotices();return originalResult}const afterUi={showLeadModal:this.showLeadModal,leadPoolFilter:clone(this.leadPoolFilter),leadQuickFilter:clone(this.leadQuickFilter)},afterRows=Array.isArray(this.leads)?this.leads:[],beforeIds=new Set(beforeLeads.map(spec=>spec.id).filter(Boolean)),newRows=afterRows.filter(row=>{const id=String(row?.id??'');return id?!beforeIds.has(id):!beforeLeads.some(spec=>spec.row===row)}).map(row=>({row,id:String(row?.id??'')})),removed=[],changedRows=[],attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),makeFieldChanges=(before,after)=>{const changes=[],keys=new Set([...Object.keys(before||{}),...Object.keys(after||{})]);for(const key of keys){const hadBefore=own(before||{},key),hadAfter=own(after||{},key),beforeValue=hadBefore?clone(before[key]):undefined,afterValue=hadAfter?clone(after[key]):undefined;if(hadBefore!==hadAfter||!same(beforeValue,afterValue))changes.push({key,hadBefore,hadAfter,before:beforeValue,after:afterValue})}return changes};for(const spec of beforeLeads){const afterRow=spec.id?afterRows.find(row=>String(row?.id??'')===spec.id)||null:afterRows.find(row=>row===spec.row)||null;if(!afterRow){removed.push(spec);continue}const changes=makeFieldChanges(spec.snapshot,clone(afterRow));if(changes.length)changedRows.push({id:spec.id,row:afterRow,changes})}for(const key of Object.keys(beforeUi))if(same(this[key],afterUi[key]))this[key]=clone(beforeUi[key]);const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const rows=Array.isArray(this.leads)?this.leads:[];for(let i=newRows.length-1;i>=0;i-=1){const spec=newRows[i],current=spec.id?rows.find(row=>String(row?.id??'')===spec.id)||null:rows.find(row=>row===spec.row)||null;if(current===spec.row){const at=rows.indexOf(current);if(at>=0)rows.splice(at,1)}}for(const spec of [...removed].sort((a,b)=>a.index-b.index)){const exists=spec.id?rows.some(row=>String(row?.id??'')===spec.id):rows.includes(spec.row);if(exists)continue;const at=Math.max(0,Math.min(spec.index,rows.length));rows.splice(at,0,clone(spec.snapshot))}for(const spec of changedRows){const current=spec.id?rows.find(row=>String(row?.id??'')===spec.id)||null:rows.find(row=>row===spec.row)||null;if(current!==spec.row)continue;for(const change of spec.changes){const hasCurrent=own(current,change.key);if(hasCurrent!==change.hadAfter)continue;if(change.hadAfter&&!same(current[change.key],change.after))continue;if(change.hadBefore)current[change.key]=clone(change.before);else delete current[change.key]}}};const applySuccessUi=()=>{for(const key of Object.keys(afterUi))if(same(this[key],beforeUi[key]))this[key]=clone(afterUi[key]);replayNotices()};if(typeof this.persistLeadSaveBarrier!=='function'){rollback();originalNotify.call(this,'线索未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistLeadSaveBarrier()).then(()=>{applySuccessUi()},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`线索未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveLead expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'LEAD_SAVE_PERSISTENCE_ACK_FINALIZE_OK: '
    'create+edit=original-validation+single-cloud-ack-before-success-ui; '
    'failure=lead+attempt-audit-rollback+rollback-persisted; '
    'concurrency=same-id-replacement+field-level+filter/modal-state-preserved; '
    'missing-barrier=fail-closed; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
