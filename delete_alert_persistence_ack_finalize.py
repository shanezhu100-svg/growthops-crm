from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('DELETE_ALERT_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistStandaloneAlertBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required shared save marker missing: ' + marker)
if 'vm.persistDeleteAlertBarrier=' in adapter:
    fail('delete alert durability barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistStandaloneAlertBarrier=()=>flushSave();',
    '  vm.persistStandaloneAlertBarrier=()=>flushSave();\n  vm.persistDeleteAlertBarrier=()=>flushSave();',
    'delete alert barrier placement',
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
    bounds = method_bounds(text, 'deleteAlert')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'if(!item)return',
        "item.typeKey==='AD_RECHARGE'",
        "title:'删除独立提醒'",
        'this.standaloneAlerts=this.standaloneAlerts.filter',
        'this.alertIgnoreFollowupText(item)',
        "title:'忽略本次到期提醒'",
        'this.dismissedAlerts.unshift',
        'this.persist()',
        "this.logAudit('删除独立提醒'",
        "this.logAudit('忽略到期提醒'",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('deleteAlert reviewed source drifted: ' + ', '.join(missing))
    if 'persistDeleteAlertBarrier' in source:
        fail('deleteAlert already ACK-aware')
    brace = source.find('{')
    if brace < 0 or not source.endswith('}'):
        fail('deleteAlert body boundary drifted')
    body = source[brace + 1:-1]
    wrapper = f"""deleteAlert(item){{const originalAsk=this.askConfirm,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);this.askConfirm=(config,action)=>originalAsk.call(this,config,()=>{{const beforeStandalone=Array.isArray(this.standaloneAlerts)?[...this.standaloneAlerts]:[],beforeDismissed=Array.isArray(this.dismissedAlerts)?[...this.dismissedAlerts]:[],beforeDismissedSet=new Set(beforeDismissed),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify,notices=[];let persistCalls=0;this.persist=()=>{{persistCalls+=1;return true}};this.notify=(...args)=>{{notices.push(args)}};let actionResult;try{{actionResult=action()}}finally{{this.persist=originalPersist;this.notify=originalNotify}}if(!persistCalls){{for(const args of notices)originalNotify.apply(this,args);return actionResult}}const afterStandalone=Array.isArray(this.standaloneAlerts)?this.standaloneAlerts:null,afterDismissed=Array.isArray(this.dismissedAlerts)?this.dismissedAlerts:null,removedRows=beforeStandalone.filter(row=>!afterStandalone||!afterStandalone.includes(row)),removedSet=new Set(removedRows),removedStandalone=removedRows.map(row=>{{const index=beforeStandalone.indexOf(row);let prev=null,next=null;for(let i=index-1;i>=0;i-=1)if(!removedSet.has(beforeStandalone[i])){{prev=beforeStandalone[i];break}}for(let i=index+1;i<beforeStandalone.length;i+=1)if(!removedSet.has(beforeStandalone[i])){{next=beforeStandalone[i];break}}return{{row,index,id:String(row?.id??''),prev,next}}}}),addedDismissed=(afterDismissed||[]).filter(row=>!beforeDismissedSet.has(row)).map(row=>({{row,snapshot:clone(row)}})),attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback=()=>{{if(Array.isArray(this.auditLogs)&&attemptAudits.length){{const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}}if(afterDismissed&&this.dismissedAlerts===afterDismissed){{for(let i=addedDismissed.length-1;i>=0;i-=1){{const spec=addedDismissed[i],at=this.dismissedAlerts.indexOf(spec.row);if(at>=0&&same(this.dismissedAlerts[at],spec.snapshot))this.dismissedAlerts.splice(at,1)}}}}if(afterStandalone&&this.standaloneAlerts===afterStandalone&&removedStandalone.length){{const authorityIds=new Set(this.standaloneAlerts.filter(row=>!removedSet.has(row)).map(row=>String(row?.id??'')).filter(Boolean));for(const spec of [...removedStandalone].sort((a,b)=>a.index-b.index)){{if(this.standaloneAlerts.includes(spec.row))continue;if(spec.id&&authorityIds.has(spec.id))continue;let at=-1;if(spec.next&&this.standaloneAlerts.includes(spec.next))at=this.standaloneAlerts.indexOf(spec.next);else if(spec.prev&&this.standaloneAlerts.includes(spec.prev))at=this.standaloneAlerts.indexOf(spec.prev)+1;else at=Math.max(0,Math.min(spec.index,this.standaloneAlerts.length));this.standaloneAlerts.splice(at,0,spec.row)}}}}}};if(typeof this.persistDeleteAlertBarrier!=='function'){{rollback();originalNotify.call(this,'提醒操作未保存：云端持久化服务不可用');return}}let barrierResult;try{{barrierResult=this.persistDeleteAlertBarrier()}}catch(e){{rollback();originalPersist.call(this);originalNotify.call(this,`提醒操作未保存：云端保存失败，已恢复原状态：${{e?.message||'保存失败'}}`);return}}return Promise.resolve(barrierResult).then(()=>{{for(const args of notices)originalNotify.apply(this,args);return actionResult}},e=>{{rollback();originalPersist.call(this);originalNotify.call(this,`提醒操作未保存：云端保存失败，已恢复原状态：${{e?.message||'保存失败'}}`)}})}});try{{const runOriginal=()=>{{{body}}};return runOriginal()}}finally{{this.askConfirm=originalAsk}}}}"""
    patched = text[:start] + wrapper + text[end:]
    path.write_text(patched, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(patched.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'deleteAlert expected in exactly one app artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'DELETE_ALERT_PERSISTENCE_ACK_FINALIZE_OK: '
    'standalone-delete+system-dismiss=confirmation-semantics-preserved+single-cloud-ack-before-success-notice; '
    'failure=attempt-row+attempt-dismissal+attempt-audit-rollback+rollback-persisted; '
    'concurrency=unrelated-row+same-id-replacement+whole-array-authority+same-key-replacement-preserved; '
    'ad-recharge=no-persist-path-unchanged; missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
