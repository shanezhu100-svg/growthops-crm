from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RENEWAL_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
        fail('saveRenewal body boundary drifted')
    return source[open_pos + 1:close_pos]


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistRechargeBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required shared save marker missing: ' + marker)
if 'vm.persistRenewalBarrier=' in adapter:
    fail('renewal durability barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistRechargeBarrier=()=>flushSave();',
    '  vm.persistRechargeBarrier=()=>flushSave();\n  vm.persistRenewalBarrier=()=>flushSave();',
    'renewal barrier placement',
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
    bounds = method_bounds(text, 'saveRenewal')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        '请选择有效的到期日期',
        '该提醒已不存在，请刷新页面后重试',
        '合同到期日期已变化，请刷新页面后重试',
        '网络环境已不存在，请刷新页面后重试',
        'this.ensureAutomaticReceivables({clientId:item.clientId,silent:true})',
        'this.dismissedAlerts=(this.dismissedAlerts||[]).filter',
        'this.persist()',
        "this.logAudit('登记续费'",
        'this.showRenewalModal=false',
        'this.renewalTarget=null',
        "this.notify(`续费已保存",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('saveRenewal reviewed source drifted: ' + ', '.join(missing))
    if 'persistRenewalBarrier' in source:
        fail('saveRenewal already ACK-aware')
    body = body_of(source)
    replacement = """saveRenewal(){const __clone=v=>v==null?v:JSON.parse(JSON.stringify(v)),__same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),__own=(o,k)=>Object.prototype.hasOwnProperty.call(o||{},k),__item=this.renewalTarget,__client=__item&&!__item.isStandalone?(this.clients||[]).find(c=>String(c.id)===String(__item.clientId))||null:null,__standalone=__item?.isStandalone?(this.standaloneAlerts||[]).find(a=>String(a.id)===String(__item.id))||null:null,__networkId=String(__item?.networkId||''),__env=__client&&__item?.typeKey==='IP'&&__networkId?(__client.networkEnvironments||[]).find(e=>String(e.id)===__networkId)||null:null,__beforeClient=__clone(__client),__beforeEnv=__clone(__env),__beforeStandalone=__clone(__standalone),__beforeHistory=Array.isArray(__client?.renewalHistory)?[...__client.renewalHistory]:[],__beforeHistorySet=new Set(__beforeHistory),__beforeReceivables=(Array.isArray(this.financeReceivables)?this.financeReceivables:[]).map((row,index)=>({row,index,id:String(row?.id??''),snapshot:__clone(row)})),__beforeDismissed=(Array.isArray(this.dismissedAlerts)?this.dismissedAlerts:[]).map((row,index)=>({row,index,snapshot:__clone(row)})),__beforeModal=this.showRenewalModal,__beforeTarget=this.renewalTarget,__auditBefore=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),__persist=this.persist,__notify=this.notify,__notes=[];let __writes=0;this.persist=()=>{__writes++;return true};this.notify=m=>{__notes.push(String(m))};let __result;try{__result=(()=>{__BODY__})()}finally{this.persist=__persist;this.notify=__notify}if(!__writes){__notes.forEach(m=>__notify.call(this,m));return __result}const __fieldChanges=(before,after,exclude=new Set())=>{const out=[],keys=new Set([...Object.keys(before||{}),...Object.keys(after||{})]);for(const key of keys){if(exclude.has(key))continue;const hb=__own(before,key),ha=__own(after,key),bv=hb?__clone(before[key]):undefined,av=ha?__clone(after[key]):undefined;if(hb!==ha||!__same(bv,av))out.push({key,hb,ha,bv,av})}return out},__applyChanges=(live,changes)=>{if(!live)return;for(const ch of changes){const hc=__own(live,ch.key);if(hc!==ch.ha)continue;if(ch.ha&&!__same(live[ch.key],ch.av))continue;if(ch.hb)live[ch.key]=__clone(ch.bv);else delete live[ch.key]}},__clientAfter=__clone(__client),__clientChanges=__fieldChanges(__beforeClient,__clientAfter,new Set(['renewalHistory','networkEnvironments'])),__envChanges=__fieldChanges(__beforeEnv,__clone(__env)),__standaloneChanges=__fieldChanges(__beforeStandalone,__clone(__standalone)),__attemptHistory=Array.isArray(__client?.renewalHistory)?__client.renewalHistory.filter(row=>!__beforeHistorySet.has(row)):[],__afterReceivables=Array.isArray(this.financeReceivables)?this.financeReceivables:[],__beforeReceivableIds=new Set(__beforeReceivables.map(x=>x.id).filter(Boolean)),__newReceivables=__afterReceivables.filter(row=>{const id=String(row?.id??'');return id?!__beforeReceivableIds.has(id):!__beforeReceivables.some(x=>x.row===row)}).map(row=>({row,id:String(row?.id??''),snapshot:__clone(row)})),__removedReceivables=[],__changedReceivables=[];for(const spec of __beforeReceivables){const live=spec.id?__afterReceivables.find(row=>String(row?.id??'')===spec.id)||null:__afterReceivables.find(row=>row===spec.row)||null;if(!live){__removedReceivables.push(spec);continue}const changes=__fieldChanges(spec.snapshot,__clone(live));if(changes.length)__changedReceivables.push({row:live,id:spec.id,changes})}const __dismissKey=row=>String(row?.key||'')||[row?.id,row?.dueDate,row?.typeKey,row?.clientId,row?.networkId].map(v=>String(v??'')).join('|'),__afterDismissed=Array.isArray(this.dismissedAlerts)?this.dismissedAlerts:[],__removedDismissed=__beforeDismissed.filter(spec=>!__afterDismissed.includes(spec.row)),__attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!__auditBefore.has(row)),__afterModal=this.showRenewalModal,__afterTarget=this.renewalTarget;if(this.showRenewalModal===__afterModal)this.showRenewalModal=__beforeModal;if(this.renewalTarget===__afterTarget)this.renewalTarget=__beforeTarget;const __rollback=()=>{if(Array.isArray(this.auditLogs)&&__attemptAudits.length){const doomed=new Set(__attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i--)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(__client){const live=(this.clients||[]).find(c=>String(c.id)===String(__client.id))||null;if(live===__client){__applyChanges(live,__clientChanges);if(Array.isArray(live.renewalHistory)&&__attemptHistory.length){const doomed=new Set(__attemptHistory);for(let i=live.renewalHistory.length-1;i>=0;i--)if(doomed.has(live.renewalHistory[i]))live.renewalHistory.splice(i,1)}if(__env){const liveEnv=(live.networkEnvironments||[]).find(e=>String(e.id)===String(__env.id))||null;if(liveEnv===__env)__applyChanges(liveEnv,__envChanges)}}}if(__standalone){const live=(this.standaloneAlerts||[]).find(a=>String(a.id)===String(__standalone.id))||null;if(live===__standalone)__applyChanges(live,__standaloneChanges)}if(Array.isArray(this.financeReceivables)){const rows=this.financeReceivables;for(let i=__newReceivables.length-1;i>=0;i--){const spec=__newReceivables[i],live=spec.id?rows.find(row=>String(row?.id??'')===spec.id)||null:rows.find(row=>row===spec.row)||null;if(live===spec.row&&__same(live,spec.snapshot)){const at=rows.indexOf(live);if(at>=0)rows.splice(at,1)}}for(const spec of [...__removedReceivables].sort((a,b)=>a.index-b.index)){const exists=spec.id?rows.some(row=>String(row?.id??'')===spec.id):rows.includes(spec.row);if(!exists)rows.splice(Math.max(0,Math.min(spec.index,rows.length)),0,__clone(spec.snapshot))}for(const spec of __changedReceivables){const live=spec.id?rows.find(row=>String(row?.id??'')===spec.id)||null:rows.find(row=>row===spec.row)||null;if(live===spec.row)__applyChanges(live,spec.changes)}}if(!Array.isArray(this.dismissedAlerts))this.dismissedAlerts=[];for(const spec of [...__removedDismissed].sort((a,b)=>a.index-b.index)){const key=__dismissKey(spec.row),exists=this.dismissedAlerts.some(row=>row===spec.row||(key&&__dismissKey(row)===key));if(!exists)this.dismissedAlerts.splice(Math.max(0,Math.min(spec.index,this.dismissedAlerts.length)),0,__clone(spec.snapshot))}};if(typeof this.persistRenewalBarrier!=='function'){__rollback();__notify.call(this,'续费未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistRenewalBarrier()).then(()=>{if(this.renewalTarget===__beforeTarget&&this.showRenewalModal===__beforeModal){this.renewalTarget=__afterTarget;this.showRenewalModal=__afterModal}__notes.forEach(m=>__notify.call(this,m))},e=>{__rollback();__persist.call(this);__notify.call(this,`续费未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}""".replace('__BODY__', body)
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'saveRenewal expected in exactly one app artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RENEWAL_PERSISTENCE_ACK_FINALIZE_OK: '
    'standalone+contract+ip=existing-validation+stale-CAS+single-cloud-ack-before-success-ui; '
    'contract-auto-receivables=helper-persists-collapsed+operation-owned-rows-rollback; '
    'failure=due-date+renewal-history+dismissed-state+receivable+attempt-audit-rollback+rollback-persisted; '
    'concurrency=client/env/standalone-replacement+field-level+history+receivable+dismissed+modal/target-authority-preserved; '
    'missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
