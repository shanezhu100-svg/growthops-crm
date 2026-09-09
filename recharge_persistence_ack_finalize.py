from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECHARGE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
        fail('saveRecharge body boundary drifted')
    return source[open_pos + 1:close_pos]


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistAdStructureBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required shared save marker missing: ' + marker)
if 'vm.persistRechargeBarrier=' in adapter:
    fail('recharge durability barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistAdStructureBarrier=()=>flushSave();',
    '  vm.persistAdStructureBarrier=()=>flushSave();\n  vm.persistRechargeBarrier=()=>flushSave();',
    'recharge barrier placement',
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
    bounds = method_bounds(text, 'saveRecharge')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'const rechargeDate=String(this.rechargeForm.date||this.localDateKey())',
        '请输入有效的充值日期',
        "this.assertMonthUnlocked(rechargeDate.slice(0,7),'登记广告充值')",
        'Number.isFinite(amount)',
        'account.rechargeHistory.unshift',
        'this.persist()',
        "this.logAudit('登记广告充值'",
        'this.showRechargeModal=false',
        "this.notify(this.hasUsdBalanceData(account)?",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('saveRecharge reviewed source drifted: ' + ', '.join(missing))
    if 'persistRechargeBarrier' in source:
        fail('saveRecharge already ACK-aware')
    body = body_of(source)
    replacement = (
        "saveRecharge(){"
        "const __clone=v=>v==null?v:JSON.parse(JSON.stringify(v)),__same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),"
        "__form=__clone(this.rechargeForm),__account=this.findAccount(__form?.clientId,__form?.platform,__form?.accountId),"
        "__beforeWasArray=Array.isArray(__account?.rechargeHistory),__beforeContainer=__beforeWasArray?null:__clone(__account?.rechargeHistory),"
        "__beforeRows=__beforeWasArray?[...__account.rechargeHistory]:[],__beforeRowSet=new Set(__beforeRows),"
        "__beforeModal=this.showRechargeModal,__auditBefore=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),"
        "__persist=this.persist,__notify=this.notify,__notes=[];let __writes=0;"
        "this.persist=()=>{__writes++;return true};this.notify=m=>{__notes.push(String(m))};let __result;"
        "try{__result=(()=>{" + body + "})()}finally{this.persist=__persist;this.notify=__notify}"
        "if(!__writes){__notes.forEach(m=>__notify.call(this,m));return __result}"
        "const __attemptRows=Array.isArray(__account?.rechargeHistory)?__account.rechargeHistory.filter(row=>!__beforeRowSet.has(row)):[],"
        "__attemptRow=__attemptRows.length===1?__attemptRows[0]:null,__attemptSnapshot=__clone(__attemptRow),"
        "__attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!__auditBefore.has(row)),__afterModal=this.showRechargeModal,"
        "__authoritativeAccount=()=>this.findAccount(__form?.clientId,__form?.platform,__form?.accountId);"
        "if(this.showRechargeModal===__afterModal)this.showRechargeModal=__beforeModal;"
        "const __rollback=()=>{"
        "if(Array.isArray(this.auditLogs)&&__attemptAudits.length){const doomed=new Set(__attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i--)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}"
        "const live=__authoritativeAccount();if(live!==__account||!Array.isArray(live?.rechargeHistory)||!__attemptRow)return;"
        "const i=live.rechargeHistory.findIndex(row=>row===__attemptRow);"
        "if(i>=0&&__same(live.rechargeHistory[i],__attemptSnapshot)){live.rechargeHistory.splice(i,1);if(!__beforeWasArray&&live.rechargeHistory.length===0)live.rechargeHistory=__clone(__beforeContainer)}};"
        "if(typeof this.persistRechargeBarrier!=='function'){__rollback();__notify.call(this,'广告充值未登记：云端持久化服务不可用');return}"
        "return Promise.resolve(this.persistRechargeBarrier()).then(()=>{"
        "if(this.showRechargeModal===__beforeModal&&__same(this.rechargeForm,__form))this.showRechargeModal=__afterModal;"
        "__notes.forEach(m=>__notify.call(this,m))"
        "},e=>{__rollback();__persist.call(this);__notify.call(this,`广告充值未登记：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})"
        "}"
    )
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveRecharge expected in exactly one app artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RECHARGE_PERSISTENCE_ACK_FINALIZE_OK: '
    'recharge=amount+date+month-lock+account-scope+cloud-ack-before-success-ui; '
    'failure=operation-owned-history-row+attempt-audit-rollback+rollback-persisted; '
    'concurrency=account-replacement+unrelated-history+same-row-field+form/modal-authority-preserved; '
    'missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
