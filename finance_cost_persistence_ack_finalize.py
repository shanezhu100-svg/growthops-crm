from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('FINANCE_COST_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistReceivableBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistFinanceCostBarrier=' in adapter:
    fail('finance cost barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistReceivableBarrier=()=>flushSave();',
    '  vm.persistReceivableBarrier=()=>flushSave();\n  vm.persistFinanceCostBarrier=()=>flushSave();',
    'finance cost barrier placement',
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

    bounds = method_bounds(text, 'saveFinanceCost')
    if bounds is not None:
        found_save += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        required = (
            'financeCostAmountCheck=',
            "this.assertMonthUnlocked(",
            'this.normalizeFinanceCost(',
            'this.financeCosts',
            'this.persist()',
            "this.logAudit(isEdit?'修改成本':'新增成本'",
            'this.showCostModal=false',
            '成本已保存',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('saveFinanceCost reviewed source drifted: ' + ', '.join(missing))
        if 'persistFinanceCostBarrier' in source:
            fail('saveFinanceCost already contains finance cost barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('saveFinanceCost body parser drifted')
        body = source[brace + 1:-1]
        replacement = """saveFinanceCost(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),initialForm=clone(this.costForm),initialId=String(initialForm?.id??''),beforeModal=this.showCostModal,beforeRows=Array.isArray(this.financeCosts)?[...this.financeCosts]:[],beforeIds=new Set(beforeRows.map(row=>String(row?.id??''))),beforeRow=initialId?beforeRows.find(row=>String(row?.id??'')===initialId)||null:null,beforeSnapshot=clone(beforeRow),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};try{const runOriginal=()=>{__BODY__};runOriginal()}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const attemptRow=initialId?(this.financeCosts||[]).find(row=>String(row?.id??'')===initialId)||null:(this.financeCosts||[]).find(row=>!beforeRows.includes(row)&&!beforeIds.has(String(row?.id??'')))||null,attemptId=String(attemptRow?.id??''),attemptSignature=attemptRow?JSON.stringify(attemptRow):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),successModal=this.showCostModal,successForm=this.costForm;this.showCostModal=beforeModal;this.costForm=clone(initialForm);const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const list=Array.isArray(this.financeCosts)?this.financeCosts:[],current=list.find(row=>String(row?.id??'')===attemptId)||null;if(initialId){if(current&&attemptSignature&&JSON.stringify(current)===attemptSignature&&beforeSnapshot){const idx=list.indexOf(current);if(idx>=0)list.splice(idx,1,clone(beforeSnapshot))}}else if(current&&attemptSignature&&JSON.stringify(current)===attemptSignature){const idx=list.indexOf(current);if(idx>=0)list.splice(idx,1)}this.showCostModal=beforeModal;this.costForm=clone(initialForm)};if(typeof this.persistFinanceCostBarrier!=='function'){rollback();originalNotify.call(this,'成本未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistFinanceCostBarrier()).then(()=>{this.showCostModal=successModal;this.costForm=successForm;for(const args of notices)originalNotify.apply(this,args)},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`成本未保存：云端保存失败，已恢复原成本状态：${e?.message||'保存失败'}`)})},""".replace('__BODY__', body)
        text = text[:start] + replacement + text[end:]

    bounds = method_bounds(text, 'deleteFinanceCost')
    if bounds is not None:
        found_delete += 1
        start, end = bounds
        source = text[start:end]
        required = (
            'const resolve=',
            'denyAuto=',
            "title:'删除成本记录'",
            'target=resolve();',
            "this.assertMonthUnlocked(String(target.date||'').slice(0,7),'删除成本')",
            'this.financeCosts=this.financeCosts.filter',
            "this.logAudit('删除成本'",
            '成本记录已删除',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('deleteFinanceCost reviewed destructive-confirmation source drifted: ' + ', '.join(missing))
        if 'persistFinanceCostBarrier' in source:
            fail('deleteFinanceCost already contains finance cost barrier')
        replacement = """deleteFinanceCost(cost){const resolve=()=>Array.isArray(this.financeCosts)?this.financeCosts.find(c=>String(c?.id)===String(cost?.id)):cost;let target=resolve();if(!target){this.notify('成本记录状态已变化，请重新操作');return}const denyAuto=c=>{if(!c?.autoGenerated)return false;this.notify(c.sourceType==='OPENING_DEAL'?'自动开户成本不能单独删除，请修改对应开户渠道':c.sourceType==='RECEIVABLE_ITEM'?'收入项目联动成本不能单独删除，请修改对应收入项目':'自动 IP / 网络成本不能单独删除，请修改客户网络环境');return true};if(denyAuto(target))return;if(!this.assertMonthUnlocked(String(target.date||'').slice(0,7),'删除成本'))return;this.askConfirm({title:'删除成本记录',message:`确定删除 ${target.date||''} 的【${this.financeCostCategoryText(target.category)} · ${this.formatMoney(target.amount,target.currency)}】吗？`,confirmText:'确认删除'},async()=>{target=resolve();if(!target){this.notify('成本记录状态已变化，请重新操作');return}if(denyAuto(target))return;if(!this.assertMonthUnlocked(String(target.date||'').slice(0,7),'删除成本'))return;if(typeof this.persistFinanceCostBarrier!=='function'){this.notify('成本记录未删除：云端持久化服务不可用');return}const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),targetId=String(target.id),rowIndex=(this.financeCosts||[]).indexOf(target),rowSnapshot=clone(target),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);this.financeCosts=this.financeCosts.filter(c=>String(c?.id)!==targetId);this.logAudit('删除成本',`${this.financeCostCategoryText(target.category)} · ${this.formatMoney(target.amount,target.currency)}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));try{await this.persistFinanceCostBarrier();this.notify('成本记录已删除，净利润已重新计算')}catch(e){if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const list=Array.isArray(this.financeCosts)?this.financeCosts:[],current=list.find(row=>String(row?.id??'')===targetId)||null;if(!current){const idx=Math.max(0,Math.min(rowIndex<0?list.length:rowIndex,list.length));list.splice(idx,0,clone(rowSnapshot))}this.persist();this.notify(`成本记录未删除：云端保存失败，已恢复原成本状态：${e?.message||'保存失败'}`)}})},"""
        text = text[:start] + replacement + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_save != 1:
    fail(f'saveFinanceCost expected in exactly one app-inline artifact, found {found_save}')
if found_delete != 1:
    fail(f'deleteFinanceCost expected in exactly one app-inline artifact, found {found_delete}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'FINANCE_COST_PERSISTENCE_ACK_FINALIZE_OK: '
    'manual-create+edit=original-validation+month-lock+cloud-ack-before-success; '
    'manual-delete=confirm-time-live-target+auto+month-lock+cloud-ack-before-success; '
    'failure=cost+attempt-audit-rollback+rollback-persisted; '
    'concurrency=id+signature+same-id-replacement-guarded; automatic-cost-paths=unchanged; '
    f'save-queue=shared-flushSave; adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
