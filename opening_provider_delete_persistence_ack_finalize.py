from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistOpeningProviderBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'deleteOpeningProvider')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'this.canManageProviders()',
        'const used=this.openingDeals.filter',
        "title:'删除开户商'",
        'this.openingProviders=this.openingProviders.filter',
        'this.persist()',
        'this.showProviderModal=false',
        "this.logAudit('删除开户商'",
        "this.notify('开户商已删除')",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('deleteOpeningProvider reviewed source drifted: ' + ', '.join(missing))
    if 'persistOpeningProviderBarrier' in source:
        fail('deleteOpeningProvider already contains opening provider barrier')
    brace = source.find('{')
    if brace < 0 or not source.endswith('}'):
        fail('deleteOpeningProvider body parser drifted')
    body = source[brace + 1:-1]
    replacement = """deleteOpeningProvider(provider){const originalAskConfirm=this.askConfirm,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),targetId=String(provider?.id??'');let confirmationResult;this.askConfirm=(config,action)=>{confirmationResult=originalAskConfirm.call(this,config,()=>{const beforeArray=Array.isArray(this.openingProviders)?this.openingProviders:null,beforeProvider=beforeArray?beforeArray.find(row=>String(row?.id??'')===targetId)||null:null,beforeProviderSnapshot=clone(beforeProvider),beforeProviderIndex=beforeArray?beforeArray.indexOf(beforeProvider):-1,beforeModal=this.showProviderModal,beforeFormRef=this.providerForm,beforeFormSnapshot=clone(this.providerForm),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[],attemptAudits=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};let actionResult;try{actionResult=action();for(const row of (Array.isArray(this.auditLogs)?this.auditLogs:[]))if(!beforeAudits.has(row))attemptAudits.push(row)}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return actionResult}const attemptArray=this.openingProviders,successModal=this.showProviderModal;this.showProviderModal=beforeModal;const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(beforeProviderSnapshot&&Array.isArray(this.openingProviders)&&this.openingProviders===attemptArray&&!this.openingProviders.some(row=>String(row?.id??'')===targetId)){const at=Math.max(0,Math.min(beforeProviderIndex<0?this.openingProviders.length:beforeProviderIndex,this.openingProviders.length));this.openingProviders.splice(at,0,clone(beforeProviderSnapshot))}};if(typeof this.persistOpeningProviderBarrier!=='function'){rollback();this.showProviderModal=beforeModal;originalNotify.call(this,'开户商未删除：云端持久化服务不可用');return}return Promise.resolve(this.persistOpeningProviderBarrier()).then(()=>{if(this.showProviderModal===beforeModal&&this.providerForm===beforeFormRef&&same(this.providerForm,beforeFormSnapshot))this.showProviderModal=successModal;for(const args of notices)originalNotify.apply(this,args)},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`开户商未删除：云端保存失败，已恢复原开户商状态：${e?.message||'保存失败'}`)})});return confirmationResult};try{const runOriginal=()=>{__BODY__};const originalResult=runOriginal();return originalResult===undefined?confirmationResult:originalResult}finally{this.askConfirm=originalAskConfirm}}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'deleteOpeningProvider expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'OPENING_PROVIDER_DELETE_PERSISTENCE_ACK_FINALIZE_OK: '
    'delete=permission+linked-deal-guard+confirmation+cloud-ack-before-success; '
    'failure=provider+attempt-audit-rollback+rollback-persisted; '
    'concurrency=unrelated-provider+same-id-replacement+whole-array+provider-form/modal-authority-preserved; '
    'missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={hashlib.sha256(adapter.encode("utf-8")).hexdigest()}; app={changed[0][0]}:{changed[0][1]}'
)
