from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistReceivablePaymentBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistReceivableBarrier=' in adapter:
    fail('receivable master barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistReceivablePaymentBarrier=()=>flushSave();',
    '  vm.persistReceivablePaymentBarrier=()=>flushSave();\n  vm.persistReceivableBarrier=()=>flushSave();',
    'receivable master barrier placement',
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

    bounds = method_bounds(text, 'saveReceivable')
    if bounds is not None:
        found_save += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        required = (
            'this.normalizeReceivable(',
            '归档客户不能新增回款账单',
            "this.assertMonthUnlocked(f.settlementMonth,'保存收入项目')",
            'this.financeReceivablePaid(f)>f.amount',
            'this.syncReceivableLinkedCost(f)',
            'this.persist()',
            'this.showReceivableModal=false',
            "this.logAudit(isEdit?'修改收入项目':'新增收入项目'",
            '收入项目已保存',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('saveReceivable reviewed source drifted: ' + ', '.join(missing))
        if 'persistReceivableBarrier' in source:
            fail('saveReceivable already contains receivable master barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('saveReceivable body parser drifted')
        body = source[brace + 1:-1]
        replacement = """saveReceivable(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),initialForm=clone(this.receivableForm),initialId=String(initialForm?.id??''),beforeModal=this.showReceivableModal,beforeRows=Array.isArray(this.financeReceivables)?[...this.financeReceivables]:[],beforeRowIds=new Set(beforeRows.map(r=>String(r?.id??''))),beforeRow=initialId?beforeRows.find(r=>String(r?.id??'')===initialId)||null:null,beforeRowSnapshot=clone(beforeRow),beforeCosts=Array.isArray(this.financeCosts)?[...this.financeCosts]:[],beforeCost=initialId?beforeCosts.find(c=>c?.sourceType==='RECEIVABLE_ITEM'&&String(c?.sourceId??'')===initialId)||null:null,beforeCostSnapshot=clone(beforeCost),beforeCostIndex=beforeCost?beforeCosts.indexOf(beforeCost):-1,beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};try{const runOriginal=()=>{__BODY__};runOriginal()}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const attemptRow=initialId?(this.financeReceivables||[]).find(r=>String(r?.id??'')===initialId)||null:(this.financeReceivables||[]).find(r=>!beforeRows.includes(r)&&!beforeRowIds.has(String(r?.id??'')))||null,attemptId=String(attemptRow?.id??''),attemptRowSignature=attemptRow?JSON.stringify(attemptRow):'',attemptCost=(this.financeCosts||[]).find(c=>c?.sourceType==='RECEIVABLE_ITEM'&&String(c?.sourceId??'')===attemptId)||null,attemptCostSignature=attemptCost?JSON.stringify(attemptCost):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),successModal=this.showReceivableModal,successForm=this.receivableForm;this.showReceivableModal=beforeModal;this.receivableForm=clone(initialForm);const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(row=>!rows.has(row))}const list=Array.isArray(this.financeReceivables)?this.financeReceivables:[],current=list.find(r=>String(r?.id??'')===attemptId)||null;if(initialId){if(current&&attemptRowSignature&&JSON.stringify(current)===attemptRowSignature&&beforeRowSnapshot){const idx=list.indexOf(current);this.financeReceivables=[...list.slice(0,idx),clone(beforeRowSnapshot),...list.slice(idx+1)]}}else if(current&&attemptRowSignature&&JSON.stringify(current)===attemptRowSignature){this.financeReceivables=list.filter(r=>r!==current)}const costList=Array.isArray(this.financeCosts)?this.financeCosts:[],currentCost=costList.find(c=>c?.sourceType==='RECEIVABLE_ITEM'&&String(c?.sourceId??'')===attemptId)||null;if(beforeCostSnapshot){if(attemptCost){if(currentCost&&attemptCostSignature&&JSON.stringify(currentCost)===attemptCostSignature){const idx=costList.indexOf(currentCost);this.financeCosts=[...costList.slice(0,idx),clone(beforeCostSnapshot),...costList.slice(idx+1)]}}else if(!currentCost){const idx=Math.max(0,Math.min(beforeCostIndex<0?costList.length:beforeCostIndex,costList.length));this.financeCosts=[...costList.slice(0,idx),clone(beforeCostSnapshot),...costList.slice(idx)]}}else if(currentCost&&attemptCost&&attemptCostSignature&&JSON.stringify(currentCost)===attemptCostSignature){this.financeCosts=costList.filter(c=>c!==currentCost)}this.showReceivableModal=beforeModal;this.receivableForm=clone(initialForm)};if(typeof this.persistReceivableBarrier!=='function'){rollback();originalNotify.call(this,'收入项目未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistReceivableBarrier()).then(()=>{this.showReceivableModal=successModal;this.receivableForm=successForm;for(const args of notices)originalNotify.apply(this,args)},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`收入项目未保存：云端保存失败，已恢复原应收与成本状态：${e?.message||'保存失败'}`)})},""".replace('__BODY__', body)
        text = text[:start] + replacement + text[end:]

    bounds = method_bounds(text, 'deleteReceivable')
    if bounds is not None:
        found_delete += 1
        start, end = bounds
        source = text[start:end]
        required = (
            'const resolve=',
            'eligible=target=>',
            "title:'删除收入项目'",
            'target=resolve();if(!eligible(target))return',
            'this.financeReceivables=this.financeReceivables.filter',
            "c.sourceType==='RECEIVABLE_ITEM'",
            "this.logAudit('删除收入项目'",
            '收入项目及关联成本已删除',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('deleteReceivable reviewed destructive-confirmation source drifted: ' + ', '.join(missing))
        if 'persistReceivableBarrier' in source:
            fail('deleteReceivable already contains receivable master barrier')
        replacement = """deleteReceivable(r){const resolve=()=>Array.isArray(this.financeReceivables)?this.financeReceivables.find(x=>String(x?.id)===String(r?.id)):r,eligible=target=>{if(!target){this.notify('收入项目状态已变化，请重新操作');return false}if(!this.assertMonthUnlocked(target.settlementMonth,'删除收入项目'))return false;if(this.financeReceivablePaid(target)>0){this.notify('该收入项目已有回款流水，不能直接删除。请保留记录或先删除回款流水。');return false}const linked=this.receivableLinkedCost(target);if(linked&&this.isMonthLocked(String(linked.date||'').slice(0,7))){this.notify('关联项目成本所在月份已月结，不能删除该收入项目');return false}return true};let target=resolve();if(!eligible(target))return;this.askConfirm({title:'删除收入项目',message:`确定删除【${this.financeReceivableClientName(target)} · ${this.financeIncomeTypeText(target.incomeType)} · ${target.projectName||target.settlementMonth}】吗？关联的项目直接成本会同步删除。`,confirmText:'确认删除'},async()=>{target=resolve();if(!eligible(target))return;if(typeof this.persistReceivableBarrier!=='function'){this.notify('收入项目未删除：云端持久化服务不可用');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),targetId=String(target.id),rowIndex=(this.financeReceivables||[]).indexOf(target),rowSnapshot=clone(target),costListBefore=Array.isArray(this.financeCosts)?[...this.financeCosts]:[],removedCosts=costListBefore.map((cost,index)=>({cost,index,snapshot:clone(cost)})).filter(item=>item.cost?.sourceType==='RECEIVABLE_ITEM'&&String(item.cost?.sourceId??'')===targetId),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);this.financeReceivables=this.financeReceivables.filter(x=>String(x?.id)!==targetId);this.financeCosts=this.financeCosts.filter(c=>!(c.sourceType==='RECEIVABLE_ITEM'&&String(c.sourceId)===targetId));this.logAudit('删除收入项目',`${this.financeReceivableClientName(target)} · ${target.settlementMonth} · ${this.financeIncomeTypeText(target.incomeType)}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));try{await this.persistReceivableBarrier();this.notify('收入项目及关联成本已删除，净利润已重新计算')}catch(e){if(Array.isArray(this.auditLogs)&&attemptAudits.length){const rows=new Set(attemptAudits);this.auditLogs=this.auditLogs.filter(row=>!rows.has(row))}let restored=false;const current=(this.financeReceivables||[]).find(x=>String(x?.id??'')===targetId)||null;if(!current){const list=Array.isArray(this.financeReceivables)?this.financeReceivables:[],idx=Math.max(0,Math.min(rowIndex<0?list.length:rowIndex,list.length));this.financeReceivables=[...list.slice(0,idx),clone(rowSnapshot),...list.slice(idx)];restored=true}if(restored&&removedCosts.length&&!this.financeCosts.some(c=>c?.sourceType==='RECEIVABLE_ITEM'&&String(c?.sourceId??'')===targetId)){let list=Array.isArray(this.financeCosts)?[...this.financeCosts]:[];for(const item of [...removedCosts].sort((a,b)=>a.index-b.index)){const idx=Math.max(0,Math.min(item.index,list.length));list=[...list.slice(0,idx),clone(item.snapshot),...list.slice(idx)]}this.financeCosts=list}this.persist();this.notify(`收入项目未删除：云端保存失败，已恢复原应收与成本状态：${e?.message||'保存失败'}`)}})},"""
        text = text[:start] + replacement + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_save != 1:
    fail(f'saveReceivable expected in exactly one app-inline artifact, found {found_save}')
if found_delete != 1:
    fail(f'deleteReceivable expected in exactly one app-inline artifact, found {found_delete}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RECEIVABLE_PERSISTENCE_ACK_FINALIZE_OK: '
    'create+edit=original-validation+linked-cost+cloud-ack-before-success; '
    'delete=confirm-time-live-target+month-lock+cloud-ack-before-success; '
    'failure=receivable+linked-cost+attempt-audit-rollback+rollback-persisted; '
    'concurrency=id+signature+same-id-replacement-guarded; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
