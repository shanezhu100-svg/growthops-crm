from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistReconciliationBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistReceivablePaymentBarrier=' in adapter:
    fail('receivable payment barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistReconciliationBarrier=()=>flushSave();',
    '  vm.persistReconciliationBarrier=()=>flushSave();\n  vm.persistReceivablePaymentBarrier=()=>flushSave();',
    'receivable payment barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found_save = 0
found_delete = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text

    bounds = method_bounds(text, 'saveReceivablePayment')
    if bounds is not None:
        found_save += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        required = (
            'this.paymentTargetReceivable',
            'this.paymentForm',
            'Number.isFinite(amount)',
            'payDateMatch=',
            'this.assertMonthUnlocked',
            'this.financeReceivableUnpaid',
            'this.persist()',
            'this.logAudit(',
            '回款流水已保存',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('saveReceivablePayment reviewed source drifted: ' + ', '.join(missing))
        if 'persistReceivablePaymentBarrier' in source:
            fail('saveReceivablePayment already contains receivable payment barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('saveReceivablePayment body parser drifted')
        body = source[brace + 1:-1]
        replacement = f"""saveReceivablePayment(){{const initialTarget=this.paymentTargetReceivable,targetId=String(initialTarget?.id??''),resolve=()=>Array.isArray(this.financeReceivables)?this.financeReceivables.find(r=>String(r?.id??'')===targetId):initialTarget,targetBefore=resolve(),beforePayments=Array.isArray(targetBefore?.payments)?[...targetBefore.payments]:[],beforePaymentRefs=new Set(beforePayments),beforePaymentIds=new Set(beforePayments.map(p=>String(p?.id??''))),beforePaidAmount=targetBefore?.paidAmount,clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),beforeModal=this.showPaymentModal,beforeForm=clone(this.paymentForm),beforePaymentTarget=this.paymentTargetReceivable,beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{{persistCalls+=1;return true}};this.notify=(...args)=>{{notices.push(args)}};try{{const runOriginal=()=>{{{body}}};runOriginal()}}finally{{this.persist=originalPersist;this.notify=originalNotify}}if(!persistCalls){{for(const args of notices)originalNotify.apply(this,args);return}}const attemptTarget=resolve(),afterPayments=Array.isArray(attemptTarget?.payments)?attemptTarget.payments:[],attemptPayment=afterPayments.find(p=>!beforePaymentRefs.has(p)&&!beforePaymentIds.has(String(p?.id??'')))||afterPayments.find(p=>!beforePaymentIds.has(String(p?.id??'')))||null,attemptPaymentId=String(attemptPayment?.id??''),attemptPaymentSignature=attemptPayment?JSON.stringify(attemptPayment):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),successModal=this.showPaymentModal,successForm=this.paymentForm,successPaymentTarget=this.paymentTargetReceivable;this.showPaymentModal=beforeModal;this.paymentForm=beforeForm;this.paymentTargetReceivable=beforePaymentTarget;const rollback=()=>{{if(Array.isArray(this.auditLogs)&&attemptAudits.length){{const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(row=>!rows.has(row))}}const current=resolve();if(current&&current===attemptTarget&&attemptPayment){{const live=(Array.isArray(current.payments)?current.payments:[]).find(p=>p===attemptPayment||String(p?.id??'')===attemptPaymentId);if(live&&(live===attemptPayment||JSON.stringify(live)===attemptPaymentSignature)){{current.payments=(current.payments||[]).filter(p=>p!==live);current.paidAmount=this.financeReceivablePaid(current);if(String(this.receivableForm?.id??'')===targetId)this.receivableForm=this.normalizeReceivable(current)}}else if(current.paidAmount===attemptTarget?.paidAmount&&beforePaidAmount!==undefined&&beforePayments.length===0)current.paidAmount=this.financeReceivablePaid(current)}}this.showPaymentModal=beforeModal;this.paymentForm=clone(beforeForm);this.paymentTargetReceivable=beforePaymentTarget}};if(typeof this.persistReceivablePaymentBarrier!=='function'){{rollback();originalNotify.call(this,'回款流水未保存：云端持久化服务不可用');return}}return Promise.resolve(this.persistReceivablePaymentBarrier()).then(()=>{{this.showPaymentModal=successModal;this.paymentForm=successForm;this.paymentTargetReceivable=successPaymentTarget;for(const args of notices)originalNotify.apply(this,args)}},e=>{{rollback();originalPersist.call(this);originalNotify.call(this,`回款流水未保存：云端保存失败，已恢复原到账状态：${{e?.message||'保存失败'}}`)}})}},"""
        text = text[:start] + replacement + text[end:]

    bounds = method_bounds(text, 'deleteReceivablePayment')
    if bounds is not None:
        found_delete += 1
        start, end = bounds
        source = text[start:end]
        required = (
            'const resolveTarget=',
            "title:'删除回款流水'",
            "this.assertMonthUnlocked(String(livePay.date||'').slice(0,7),'删除该到账月份的回款')",
            'target.payments=(target.payments||[]).filter',
            'target.paidAmount=this.financeReceivablePaid(target)',
            "this.logAudit('删除回款流水'",
            "this.notify('回款流水已删除')",
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('deleteReceivablePayment reviewed destructive-confirmation source drifted: ' + ', '.join(missing))
        if 'persistReceivablePaymentBarrier' in source:
            fail('deleteReceivablePayment already contains receivable payment barrier')
        replacement = """deleteReceivablePayment(r,pay){const resolveTarget=()=>Array.isArray(this.financeReceivables)?this.financeReceivables.find(x=>String(x?.id)===String(r?.id)):r,resolvePay=target=>(target?.payments||[]).find(p=>String(p?.id)===String(pay?.id));let target=resolveTarget(),livePay=resolvePay(target);if(!target||!livePay){if(r&&pay)this.notify('回款流水状态已变化，请重新操作');return}if(!this.assertMonthUnlocked(String(livePay.date||'').slice(0,7),'删除该到账月份的回款'))return;this.askConfirm({title:'删除回款流水',message:`确定删除 ${livePay.date} 的回款 ${this.formatMoney(livePay.amount,target.currency)} 吗？删除后已收与未收金额会自动重新计算。`,confirmText:'确认删除'},async()=>{target=resolveTarget();livePay=resolvePay(target);if(!target||!livePay){this.notify('回款流水状态已变化，请重新操作');return}if(!this.assertMonthUnlocked(String(livePay.date||'').slice(0,7),'删除该到账月份的回款'))return;if(typeof this.persistReceivablePaymentBarrier!=='function'){this.notify('回款流水未删除：云端持久化服务不可用');return}const targetRef=target,beforePayments=[...(target.payments||[])],removedIndex=beforePayments.indexOf(livePay),removedPay=livePay,removedPayId=String(removedPay?.id??''),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);target.payments=(target.payments||[]).filter(p=>String(p?.id)!==removedPayId);target.paidAmount=this.financeReceivablePaid(target);if(String(this.receivableForm?.id)===String(target.id))this.receivableForm=this.normalizeReceivable(target);this.logAudit('删除回款流水',`${this.financeReceivableClientName(target)} · ${removedPay.date} · ${this.formatMoney(removedPay.amount,target.currency)}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));try{await this.persistReceivablePaymentBarrier();this.notify('回款流水已删除')}catch(e){if(Array.isArray(this.auditLogs)&&attemptAudits.length){const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(row=>!rows.has(row))}const current=resolveTarget();if(current===targetRef&&!resolvePay(current)){const payments=Array.isArray(current.payments)?current.payments:[],insertAt=Math.max(0,Math.min(removedIndex<0?payments.length:removedIndex,payments.length));current.payments=[...payments.slice(0,insertAt),removedPay,...payments.slice(insertAt)];current.paidAmount=this.financeReceivablePaid(current);if(String(this.receivableForm?.id)===String(current.id))this.receivableForm=this.normalizeReceivable(current)}this.persist();this.notify(`回款流水未删除：云端保存失败，已恢复原到账状态：${e?.message||'保存失败'}`)}})},"""
        text = text[:start] + replacement + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_save != 1:
    fail(f'saveReceivablePayment expected in exactly one app-inline artifact, found {found_save}')
if found_delete != 1:
    fail(f'deleteReceivablePayment expected in exactly one app-inline artifact, found {found_delete}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RECEIVABLE_PAYMENT_PERSISTENCE_ACK_FINALIZE_OK: '
    'save=original-validation+payment-ledger+cloud-ack-before-success; '
    'delete=confirm-time-live-payment+month-lock+cloud-ack-before-success; '
    'failure=payment+paid-total+attempt-audit-rollback+rollback-persisted; '
    'concurrency=receivable-identity+payment-id+same-id-replacement-guarded; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
