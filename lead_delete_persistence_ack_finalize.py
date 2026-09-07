from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('LEAD_DELETE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistLeadSaveBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistLeadDeleteBarrier=' in adapter:
    fail('lead delete barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistLeadSaveBarrier=()=>flushSave();',
    '  vm.persistLeadSaveBarrier=()=>flushSave();\n  vm.persistLeadDeleteBarrier=()=>flushSave();',
    'lead delete barrier placement',
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
    bounds = method_bounds(text, 'deleteLead')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'const resolve=()=>Array.isArray(this.leads)?this.leads.find',
        'target=resolve()',
        'this.askConfirm(',
        'this.leads=this.leads.filter',
        'this.persist()',
        "this.logAudit('删除潜在客户'",
        'this.notify(',
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('deleteLead reviewed source drifted: ' + ', '.join(missing))
    if 'persistLeadDeleteBarrier' in source:
        fail('deleteLead already contains durability barrier')
    brace = source.find('{')
    if brace < 0 or not source.endswith('}'):
        fail('deleteLead body parser drifted')
    body = source[brace + 1:-1]
    replacement = """deleteLead(lead){const originalAsk=this.askConfirm,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),targetId=String(lead?.id??'');this.askConfirm=(config,action)=>originalAsk.call(this,config,()=>{const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify,rowsBefore=Array.isArray(this.leads)?this.leads:[],removed=rowsBefore.map((row,index)=>({row,index,id:String(row?.id??''),snapshot:clone(row)})).filter(spec=>spec.id===targetId);let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};let actionResult;try{actionResult=action()}finally{this.persist=originalPersist;this.notify=originalNotify}const replayNotices=()=>{for(const args of notices)originalNotify.apply(this,args)},attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));if(!persistCalls){replayNotices();return actionResult}const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const rows=Array.isArray(this.leads)?this.leads:[];if(!rows.some(row=>String(row?.id??'')===targetId)){for(const spec of [...removed].sort((a,b)=>a.index-b.index)){const at=Math.max(0,Math.min(spec.index,rows.length));rows.splice(at,0,clone(spec.snapshot))}}};if(typeof this.persistLeadDeleteBarrier!=='function'){rollback();originalNotify.call(this,'线索删除未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistLeadDeleteBarrier()).then(()=>{replayNotices()},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`线索删除未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})});try{const runOriginal=()=>{__BODY__};return runOriginal()}finally{this.askConfirm=originalAsk}}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'deleteLead expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'LEAD_DELETE_PERSISTENCE_ACK_FINALIZE_OK: '
    'delete=live-record-confirmation+single-cloud-ack-before-success; '
    'failure=lead+attempt-audit-rollback+rollback-persisted; '
    'concurrency=same-id-replacement+unrelated-leads+unrelated-audit-preserved; '
    'missing-barrier=fail-closed; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
