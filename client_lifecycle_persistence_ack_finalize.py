from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('CLIENT_LIFECYCLE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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


if not ADAPTER.is_file(): fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistOpeningProviderBarrier=()=>flushSave();'):
    if marker not in adapter: fail('required final adapter marker missing: ' + marker)
if 'vm.persistClientLifecycleBarrier=' in adapter: fail('client lifecycle barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistOpeningProviderBarrier=()=>flushSave();',
    '  vm.persistOpeningProviderBarrier=()=>flushSave();\n  vm.persistClientLifecycleBarrier=()=>flushSave();',
    'client lifecycle barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir(): fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files: fail('no final app-inline JS artifacts')

specs = {
    'archiveClient': {
        'arg': 'client',
        'collection': 'clients',
        'required': ("title:'归档客户'", "this.canArchiveClients()", "target.archived=true", "this.logAudit('归档客户'"),
        'failure': '客户归档未保存',
    },
    'restoreClient': {
        'arg': 'client',
        'collection': 'clients',
        'required': ("title:'恢复归档客户'", "this.canArchiveClients()", "target.archived=false", "this.logAudit('恢复归档客户'"),
        'failure': '客户恢复未保存',
    },
    'deleteLead': {
        'arg': 'lead',
        'collection': 'leads',
        'required': ("title:'删除潜在客户'", "this.leads=this.leads.filter", "this.logAudit('删除潜在客户'"),
        'failure': '潜在客户删除未保存',
    },
}

changed = []
counts = {name: 0 for name in specs}
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, spec in specs.items():
        bounds = method_bounds(text, name)
        if bounds is None: continue
        counts[name] += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        missing = [marker for marker in spec['required'] if marker not in source]
        if missing: fail(f'{name} reviewed source drifted: ' + ', '.join(missing))
        if 'persistClientLifecycleBarrier' in source: fail(f'{name} already contains durability barrier')
        brace = source.find('{')
        body = source[brace + 1:-1]
        arg = spec['arg']
        collection = spec['collection']
        failure = spec['failure']
        is_delete = name == 'deleteLead'
        rollback_js = (
            "const rows=Array.isArray(this.leads)?this.leads:[],current=rows.find(row=>String(row?.id??'')===targetId)||null;"
            "if(!current&&beforeSnapshot){const at=Math.max(0,Math.min(beforeIndex,rows.length));rows.splice(at,0,clone(beforeSnapshot))}"
            if is_delete else
            "const rows=Array.isArray(this.clients)?this.clients:[],current=rows.find(row=>String(row?.id??'')===targetId)||null;"
            "if(current===attemptRow){for(const change of fieldChanges){const hasCurrent=own(current,change.key);if(hasCurrent!==change.hadAfter)continue;if(change.hadAfter&&!same(current[change.key],change.after))continue;if(change.hadBefore)current[change.key]=clone(change.before);else delete current[change.key]}}"
        )
        wrapper = f"""{name}({arg}){{const originalAsk=this.askConfirm,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key),targetId=String({arg}?.id??'');this.askConfirm=(config,action)=>originalAsk.call(this,config,()=>{{const rowsBefore=Array.isArray(this.{collection})?this.{collection}:[],beforeRow=rowsBefore.find(row=>String(row?.id??'')===targetId)||({arg}||null),beforeSnapshot=clone(beforeRow),beforeIndex=rowsBefore.indexOf(beforeRow),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[],attemptAudits=[];this.persist=()=>{{persistCalls+=1;return true}};this.notify=(...args)=>{{notices.push(args)}};let actionResult;try{{actionResult=action();for(const row of (Array.isArray(this.auditLogs)?this.auditLogs:[]))if(!beforeAudits.has(row))attemptAudits.push(row)}}finally{{this.persist=originalPersist;this.notify=originalNotify}}if(!persistCalls){{for(const args of notices)originalNotify.apply(this,args);return actionResult}}const rowsAfter=Array.isArray(this.{collection})?this.{collection}:[],attemptRow=rowsAfter.find(row=>String(row?.id??'')===targetId)||null,fieldChanges=[];if(beforeSnapshot&&attemptRow){{const keys=new Set([...Object.keys(beforeSnapshot||{{}}),...Object.keys(attemptRow||{{}})]);for(const key of keys){{const hadBefore=own(beforeSnapshot,key),hadAfter=own(attemptRow,key),beforeValue=hadBefore?clone(beforeSnapshot[key]):undefined,afterValue=hadAfter?clone(attemptRow[key]):undefined;if(hadBefore!==hadAfter||!same(beforeValue,afterValue))fieldChanges.push({{key,hadBefore,hadAfter,before:beforeValue,after:afterValue}})}}}}const rollback=()=>{{if(Array.isArray(this.auditLogs)&&attemptAudits.length){{const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}}{rollback_js}}};if(typeof this.persistClientLifecycleBarrier!=='function'){{rollback();originalNotify.call(this,'{failure}：云端持久化服务不可用');return}}return Promise.resolve(this.persistClientLifecycleBarrier()).then(()=>{{for(const args of notices)originalNotify.apply(this,args)}},e=>{{rollback();originalPersist.call(this);originalNotify.call(this,`{failure}：云端保存失败，已恢复原状态：${{e?.message||'保存失败'}}`)}})}});try{{const runOriginal=()=>{{{body}}};return runOriginal()}}finally{{this.askConfirm=originalAsk}}}}"""
        text = text[:start] + wrapper + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in counts.items():
    if count != 1: fail(f'{name} expected in exactly one app artifact, found {count}')
if len(changed) != 1: fail(f'expected exactly one changed app artifact, found {len(changed)}')
print(
    'CLIENT_LIFECYCLE_PERSISTENCE_ACK_FINALIZE_OK: '
    'archive+restore+lead-delete=original-confirm-time-authority+cloud-ack-before-success; '
    'failure=lifecycle-or-lead+attempt-audit-rollback+rollback-persisted; '
    'concurrency=object+field-compare+same-id-replacement-guarded; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
