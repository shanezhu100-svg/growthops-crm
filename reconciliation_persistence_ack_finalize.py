from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECONCILIATION_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


def method_bounds(text: str, name: str):
    signature = re.compile(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', re.M)
    match = signature.search(text)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    tail = text[start:]
    defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
    if len(defs) < 2 or defs[0].group(1) != name:
        fail(f'{name} boundary parser drifted')
    end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
    return start, end


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistFinanceMonthLockBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistReconciliationBarrier=' in adapter:
    fail('reconciliation barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistFinanceMonthLockBarrier=()=>flushSave();',
    '  vm.persistFinanceMonthLockBarrier=()=>flushSave();\n  vm.persistReconciliationBarrier=()=>flushSave();',
    'reconciliation barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found_save = 0
found_void = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text

    bounds = method_bounds(text, 'saveReconciliation')
    if bounds is not None:
        found_save += 1
        start, end = bounds
        source = text[start:end].rstrip(',').strip()
        required = (
            'this.reconciliationSelectedOption',
            'this.reconciliationForm',
            'this.assertMonthUnlocked',
            'this.financeReconciliations',
            'this.financeActualRebates',
            "this.logAudit('代理商返点对账'",
            "this.notify('对账已确认",
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('saveReconciliation reviewed source drifted: ' + ', '.join(missing))
        if 'persistReconciliationBarrier' in source:
            fail('saveReconciliation already contains reconciliation barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('saveReconciliation body parser drifted')
        body = source[brace + 1:-1]
        replacement = f"""async saveReconciliation(){{const keyOpt=this.reconciliationSelectedOption,keyForm=this.reconciliationForm||{{}},keyProvider=String(keyOpt?.providerId??''),keyContact=String(keyOpt?.contactId??''),keyMonth=String(keyForm.settlementMonth||''),keyCurrency=String(keyForm.currency||'USD'),sameRec=r=>String(r?.providerId??'')===keyProvider&&String(r?.contactId??'')===keyContact&&String(r?.settlementMonth||'')===keyMonth&&String(r?.currency||'USD')===keyCurrency,sameActual=r=>String(r?.providerId??'')===keyProvider&&String(r?.contactId??'')===keyContact&&String(r?.settlementMonth||'')===keyMonth&&String(r?.currency||'USD')===keyCurrency,priorRec=(Array.isArray(this.financeReconciliations)?this.financeReconciliations:[]).find(sameRec)||null,priorRecClone=priorRec?JSON.parse(JSON.stringify(priorRec)):null,priorActual=(Array.isArray(this.financeActualRebates)?this.financeActualRebates:[]).filter(sameActual).map(r=>JSON.parse(JSON.stringify(r))),priorModal=this.showReconciliationModal,priorAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0,notices=[];this.persist=()=>{{persistCalls+=1;return true}};this.notify=message=>{{notices.push(message)}};try{{const runOriginal=()=>{{{body}}};runOriginal()}}finally{{this.persist=originalPersist;this.notify=originalNotify}}if(!persistCalls){{for(const message of notices)originalNotify.call(this,message);return}}const attemptRec=(Array.isArray(this.financeReconciliations)?this.financeReconciliations:[]).find(sameRec)||null,attemptRecSnapshot=attemptRec?JSON.stringify(attemptRec):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!priorAudits.has(row)),successModal=this.showReconciliationModal;this.showReconciliationModal=priorModal;const rollback=()=>{{if(Array.isArray(this.auditLogs)&&attemptAudits.length){{const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(row=>!rows.has(row))}}const current=(Array.isArray(this.financeReconciliations)?this.financeReconciliations:[]).find(sameRec)||null;if(current&&current===attemptRec&&JSON.stringify(current)===attemptRecSnapshot){{if(priorRecClone){{const i=this.financeReconciliations.indexOf(current);if(i>=0)this.financeReconciliations.splice(i,1,priorRecClone)}}else this.financeReconciliations=this.financeReconciliations.filter(r=>r!==current)}}else if(!current&&priorRecClone)this.financeReconciliations.push(priorRecClone);const liveActual=(Array.isArray(this.financeActualRebates)?this.financeActualRebates:[]).filter(sameActual);if(!liveActual.length&&priorActual.length)this.financeActualRebates.push(...priorActual);this.showReconciliationModal=priorModal}};if(typeof this.persistReconciliationBarrier!=='function'){{rollback();originalNotify.call(this,'返点对账未执行：云端持久化服务不可用');return}}try{{await this.persistReconciliationBarrier();this.showReconciliationModal=successModal;for(const message of notices)originalNotify.call(this,message)}}catch(e){{rollback();originalPersist.call(this);originalNotify.call(this,`返点对账未完成：云端保存失败，已恢复原会计状态：${{e?.message||'保存失败'}}`)}}}},"""
        text = text[:start] + replacement + text[end:]

    bounds = method_bounds(text, 'voidReconciliation')
    if bounds is not None:
        found_void += 1
        start, end = bounds
        source = text[start:end]
        required = (
            "title:'撤销返点对账'",
            "this.assertMonthUnlocked(rec.settlementMonth,'撤销返点对账')",
            "rec.status='VOID'",
            "this.logAudit('撤销代理商返点对账'",
            "this.notify('返点对账已撤销，实际返点与利润已重新计算')",
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('voidReconciliation reviewed destructive-confirmation source drifted: ' + ', '.join(missing))
        if 'persistReconciliationBarrier' in source:
            fail('voidReconciliation already contains reconciliation barrier')
        replacement = """voidReconciliation(row){const initial=row?.record,resolve=()=>Array.isArray(this.financeReconciliations)?this.financeReconciliations.find(r=>String(r?.id)===String(initial?.id)):initial;let rec=resolve();if(!rec||rec.status==='VOID')return;if(!this.assertMonthUnlocked(rec.settlementMonth,'撤销返点对账'))return;this.askConfirm({title:'撤销返点对账',message:`确定撤销 ${row.providerName} / ${row.contactName} · ${rec.settlementMonth} 的返点对账吗？实际返点将从财务利润中移除。`,confirmText:'确认撤销',tone:'warning'},async()=>{rec=resolve();if(!rec||rec.status==='VOID'){this.notify('对账状态已变化，请重新操作');return}if(!this.assertMonthUnlocked(rec.settlementMonth,'撤销返点对账'))return;if(typeof this.persistReconciliationBarrier!=='function'){this.notify('撤销返点对账未执行：云端持久化服务不可用');return}const previous=JSON.parse(JSON.stringify(rec)),sameActual=r=>String(r?.providerId)===String(rec.providerId)&&String(r?.contactId)===String(rec.contactId)&&r.settlementMonth===rec.settlementMonth&&(r.currency||'USD')===(rec.currency||'USD'),removed=(Array.isArray(this.financeActualRebates)?this.financeActualRebates:[]).filter(sameActual).map(r=>JSON.parse(JSON.stringify(r))),priorAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);rec.status='VOID';rec.voidedAt=new Date().toISOString();rec.voidedBy=this.currentUser?.name||'';const attemptVoid={status:rec.status,voidedAt:rec.voidedAt,voidedBy:rec.voidedBy};this.financeActualRebates=this.financeActualRebates.filter(r=>!sameActual(r));this.logAudit('撤销代理商返点对账',`${row.providerName} / ${row.contactName} · ${rec.settlementMonth}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(a=>!priorAudits.has(a));try{await this.persistReconciliationBarrier();this.notify('返点对账已撤销，实际返点与利润已重新计算')}catch(e){if(Array.isArray(this.auditLogs)&&attemptAudits.length){const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(a=>!rows.has(a))}const current=resolve();if(current===rec&&current.status===attemptVoid.status&&current.voidedAt===attemptVoid.voidedAt&&current.voidedBy===attemptVoid.voidedBy){for(const key of Object.keys(current))if(!Object.prototype.hasOwnProperty.call(previous,key))delete current[key];Object.assign(current,previous)}if(!(Array.isArray(this.financeActualRebates)?this.financeActualRebates:[]).some(sameActual)&&removed.length)this.financeActualRebates.push(...removed);this.persist();this.notify(`撤销返点对账未完成：云端保存失败，已恢复原会计状态：${e?.message||'保存失败'}`)}})},"""
        text = text[:start] + replacement + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_save != 1:
    fail(f'saveReconciliation expected in exactly one app-inline artifact, found {found_save}')
if found_void != 1:
    fail(f'voidReconciliation expected in exactly one app-inline artifact, found {found_void}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RECONCILIATION_PERSISTENCE_ACK_FINALIZE_OK: '
    'save=original-business-logic+cloud-ack-before-modal-success; '
    'void=confirm-time-live-status+month-lock+cloud-ack-before-success; '
    'failure=reconciliation+actual-rebate+attempt-audit-rollback+rollback-persisted; '
    'concurrency=key/identity/signature-guarded+unrelated-state-preserved; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
