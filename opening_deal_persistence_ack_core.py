from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_DEAL_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
            if depth < 0:
                break
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistFinanceCostBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistOpeningDealBarrier=' in adapter:
    fail('opening deal barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistFinanceCostBarrier=()=>flushSave();',
    '  vm.persistFinanceCostBarrier=()=>flushSave();\n  vm.persistOpeningDealBarrier=()=>flushSave();',
    'opening deal barrier placement',
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

    bounds = method_bounds(text, 'saveOpeningDeal')
    if bounds is not None:
        found_save += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        required = (
            '该开户渠道记录已不存在',
            'syncOpeningFeeCost',
            'this.openingDeals',
            'this.persist()',
            'this.logAudit(',
            'this.showOpeningModal=false',
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('saveOpeningDeal reviewed source drifted: ' + ', '.join(missing))
        if 'persistOpeningDealBarrier' in source:
            fail('saveOpeningDeal already contains opening deal barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('saveOpeningDeal body parser drifted')
        body = source[brace + 1:-1]
        replacement = """saveOpeningDeal(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),initialForm=clone(this.openingForm),initialId=String(initialForm?.id??''),beforeModal=this.showOpeningModal,beforeDeals=Array.isArray(this.openingDeals)?[...this.openingDeals]:[],beforeDealIds=new Set(beforeDeals.map(row=>String(row?.id??''))),beforeDeal=initialId?beforeDeals.find(row=>String(row?.id??'')===initialId)||null:null,beforeDealSnapshot=clone(beforeDeal),beforeCosts=Array.isArray(this.financeCosts)?[...this.financeCosts]:[],beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};try{const runOriginal=()=>{__BODY__};runOriginal()}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const attemptDeal=initialId?(this.openingDeals||[]).find(row=>String(row?.id??'')===initialId)||null:(this.openingDeals||[]).find(row=>!beforeDeals.includes(row)&&!beforeDealIds.has(String(row?.id??'')))||null,attemptId=String(attemptDeal?.id??''),attemptDealSignature=attemptDeal?JSON.stringify(attemptDeal):'',beforeCost=beforeCosts.find(row=>row?.sourceType==='OPENING_DEAL'&&String(row?.sourceId??'')===attemptId)||null,beforeCostSnapshot=clone(beforeCost),attemptCost=(this.financeCosts||[]).find(row=>row?.sourceType==='OPENING_DEAL'&&String(row?.sourceId??'')===attemptId)||null,attemptCostSignature=attemptCost?JSON.stringify(attemptCost):'',attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),successModal=this.showOpeningModal,successForm=this.openingForm;this.showOpeningModal=beforeModal;this.openingForm=clone(initialForm);const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const deals=Array.isArray(this.openingDeals)?this.openingDeals:[],currentDeal=deals.find(row=>String(row?.id??'')===attemptId)||null;if(initialId){if(currentDeal&&attemptDealSignature&&JSON.stringify(currentDeal)===attemptDealSignature&&beforeDealSnapshot){const idx=deals.indexOf(currentDeal);if(idx>=0)deals.splice(idx,1,clone(beforeDealSnapshot))}}else if(currentDeal&&attemptDealSignature&&JSON.stringify(currentDeal)===attemptDealSignature){const idx=deals.indexOf(currentDeal);if(idx>=0)deals.splice(idx,1)}const costs=Array.isArray(this.financeCosts)?this.financeCosts:[],currentCost=costs.find(row=>row?.sourceType==='OPENING_DEAL'&&String(row?.sourceId??'')===attemptId)||null;if(beforeCostSnapshot){if(currentCost&&attemptCostSignature&&JSON.stringify(currentCost)===attemptCostSignature){const idx=costs.indexOf(currentCost);if(idx>=0)costs.splice(idx,1,clone(beforeCostSnapshot))}}else if(currentCost&&attemptCostSignature&&JSON.stringify(currentCost)===attemptCostSignature){const idx=costs.indexOf(currentCost);if(idx>=0)costs.splice(idx,1)}this.showOpeningModal=beforeModal;this.openingForm=clone(initialForm)};if(typeof this.persistOpeningDealBarrier!=='function'){rollback();originalNotify.call(this,'开户渠道记录未保存：云端持久化服务不可用');return}return Promise.resolve(this.persistOpeningDealBarrier()).then(()=>{this.showOpeningModal=successModal;this.openingForm=successForm;for(const args of notices)originalNotify.apply(this,args)},e=>{rollback();originalPersist.call(this);originalNotify.call(this,`开户渠道记录未保存：云端保存失败，已恢复原开户与关联成本状态：${e?.message||'保存失败'}`)})}""".replace('__BODY__', body)
        text = text[:start] + replacement + text[end:]

    bounds = method_bounds(text, 'deleteOpeningDeal')
    if bounds is not None:
        found_delete += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        required = (
            'linkedCostLocked=',
            "title:'删除客户开户渠道记录'",
            'this.openingDeals=this.openingDeals.filter',
            'this.financeCosts=this.financeCosts.filter',
            'this.persist()',
            "this.logAudit('删除客户开户渠道'",
        )
        missing = [marker for marker in required if marker not in source]
        if missing:
            fail('deleteOpeningDeal reviewed source drifted: ' + ', '.join(missing))
        if 'persistOpeningDealBarrier' in source:
            fail('deleteOpeningDeal already contains opening deal barrier')
        brace = source.find('{')
        if brace < 0 or not source.endswith('}'):
            fail('deleteOpeningDeal body parser drifted')
        body = source[brace + 1:-1]
        replacement = """deleteOpeningDeal(deal){const originalAskConfirm=this.askConfirm;this.askConfirm=(config,action)=>originalAskConfirm.call(this,config,async()=>{const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),targetId=String(deal?.id??''),beforeDeals=Array.isArray(this.openingDeals)?[...this.openingDeals]:[],beforeDeal=beforeDeals.find(row=>String(row?.id??'')===targetId)||null,beforeDealSnapshot=clone(beforeDeal),dealIndex=beforeDeals.indexOf(beforeDeal),beforeCosts=Array.isArray(this.financeCosts)?[...this.financeCosts]:[],beforeCost=beforeCosts.find(row=>row?.sourceType==='OPENING_DEAL'&&String(row?.sourceId??'')===targetId)||null,beforeCostSnapshot=clone(beforeCost),costIndex=beforeCosts.indexOf(beforeCost),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist,originalNotify=this.notify;let persistCalls=0;const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};try{await Promise.resolve(action())}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const deals=Array.isArray(this.openingDeals)?this.openingDeals:[],currentDeal=deals.find(row=>String(row?.id??'')===targetId)||null;if(beforeDealSnapshot&&!currentDeal){const idx=Math.max(0,Math.min(dealIndex<0?deals.length:dealIndex,deals.length));deals.splice(idx,0,clone(beforeDealSnapshot))}const costs=Array.isArray(this.financeCosts)?this.financeCosts:[],currentCost=costs.find(row=>row?.sourceType==='OPENING_DEAL'&&String(row?.sourceId??'')===targetId)||null;if(beforeCostSnapshot&&!currentCost){const idx=Math.max(0,Math.min(costIndex<0?costs.length:costIndex,costs.length));costs.splice(idx,0,clone(beforeCostSnapshot))}};if(typeof this.persistOpeningDealBarrier!=='function'){rollback();originalNotify.call(this,'开户渠道记录未删除：云端持久化服务不可用');return}try{await this.persistOpeningDealBarrier();for(const args of notices)originalNotify.apply(this,args)}catch(e){rollback();originalPersist.call(this);originalNotify.call(this,`开户渠道记录未删除：云端保存失败，已恢复原开户与关联成本状态：${e?.message||'保存失败'}`)}});try{const runOriginal=()=>{__BODY__};return runOriginal()}finally{this.askConfirm=originalAskConfirm}}""".replace('__BODY__', body)
        text = text[:start] + replacement + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_save != 1:
    fail(f'saveOpeningDeal expected in exactly one app-inline artifact, found {found_save}')
if found_delete != 1:
    fail(f'deleteOpeningDeal expected in exactly one app-inline artifact, found {found_delete}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'OPENING_DEAL_PERSISTENCE_ACK_FINALIZE_OK: '
    'create+edit=original-validation+linked-opening-cost+cloud-ack-before-success; '
    'delete=original-confirm-time-lock+atomic-source-cost-delete+cloud-ack-before-success; '
    'failure=deal+linked-cost+attempt-audit-rollback+rollback-persisted; '
    'concurrency=deal-signature+same-id-replacement+linked-cost-source-identity-guarded; '
    f'provider-paths=unchanged; save-queue=shared-flushSave; adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
