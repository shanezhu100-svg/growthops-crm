from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('STANDALONE_ALERT_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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


def body_of(source: str) -> str:
    open_pos = source.find('{')
    close_pos = source.rfind('}')
    if open_pos < 0 or close_pos <= open_pos:
        fail('saveStandaloneAlert body boundary drifted')
    return source[open_pos + 1:close_pos]


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistRenewalBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required shared save marker missing: ' + marker)
if 'vm.persistStandaloneAlertBarrier=' in adapter:
    fail('standalone alert durability barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistRenewalBarrier=()=>flushSave();',
    '  vm.persistRenewalBarrier=()=>flushSave();\n  vm.persistStandaloneAlertBarrier=()=>flushSave();',
    'standalone alert barrier placement',
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
    bounds = method_bounds(text, 'saveStandaloneAlert')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        '请选择有效的提醒类型',
        '请选择有效的到期日期',
        'this.standaloneAlerts.unshift(record)',
        'this.persist()',
        "this.logAudit('新增独立提醒'",
        'this.showAddAlertModal=false',
        "this.newAlertForm={typeKey:'IP',clientName:'',dueDate:'',cost:'',target:''}",
        "this.notify('独立提醒已添加",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('saveStandaloneAlert reviewed source drifted: ' + ', '.join(missing))
    if 'persistStandaloneAlertBarrier' in source:
        fail('saveStandaloneAlert already ACK-aware')
    body = body_of(source)
    replacement = """saveStandaloneAlert(){const __clone=v=>v==null?v:JSON.parse(JSON.stringify(v)),__same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),__beforeRows=Array.isArray(this.standaloneAlerts)?[...this.standaloneAlerts]:[],__beforeSet=new Set(__beforeRows),__beforeForm=this.newAlertForm,__beforeFormSnapshot=__clone(this.newAlertForm),__beforeModal=this.showAddAlertModal,__auditBefore=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),__persist=this.persist,__notify=this.notify,__notes=[];let __writes=0;this.persist=()=>{__writes++;return true};this.notify=m=>{__notes.push(String(m))};let __result;try{__result=(()=>{__BODY__})()}finally{this.persist=__persist;this.notify=__notify}if(!__writes){__notes.forEach(m=>__notify.call(this,m));return __result}const __afterRows=Array.isArray(this.standaloneAlerts)?this.standaloneAlerts:[],__attemptRows=__afterRows.filter(row=>!__beforeSet.has(row)).map(row=>({row,id:String(row?.id??''),snapshot:__clone(row)})),__attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!__auditBefore.has(row)),__afterForm=this.newAlertForm,__afterModal=this.showAddAlertModal;if(this.newAlertForm===__afterForm)this.newAlertForm=__beforeForm;if(this.showAddAlertModal===__afterModal)this.showAddAlertModal=__beforeModal;const __rollback=()=>{if(Array.isArray(this.auditLogs)&&__attemptAudits.length){const doomed=new Set(__attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i--)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(Array.isArray(this.standaloneAlerts)){for(let i=__attemptRows.length-1;i>=0;i--){const spec=__attemptRows[i],live=spec.id?this.standaloneAlerts.find(row=>String(row?.id??'')===spec.id)||null:this.standaloneAlerts.find(row=>row===spec.row)||null;if(live===spec.row&&__same(live,spec.snapshot)){const at=this.standaloneAlerts.indexOf(live);if(at>=0)this.standaloneAlerts.splice(at,1)}}}};if(typeof this.persistStandaloneAlertBarrier!=='function'){__rollback();__notify.call(this,'独立提醒未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistStandaloneAlertBarrier()).then(()=>{const __formUntouched=this.newAlertForm===__beforeForm&&__same(this.newAlertForm,__beforeFormSnapshot);if(__formUntouched&&this.showAddAlertModal===__beforeModal){this.newAlertForm=__afterForm;this.showAddAlertModal=__afterModal}__notes.forEach(m=>__notify.call(this,m))},e=>{__rollback();__persist.call(this);__notify.call(this,`独立提醒未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveStandaloneAlert expected in exactly one app artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'STANDALONE_ALERT_PERSISTENCE_ACK_FINALIZE_OK: '
    'create=type+calendar-validation+single-cloud-ack-before-success-ui; '
    'failure=operation-owned-row+attempt-audit-rollback+rollback-persisted; '
    'concurrency=unrelated-row+same-id-replacement+form/modal-authority-preserved; '
    'missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
