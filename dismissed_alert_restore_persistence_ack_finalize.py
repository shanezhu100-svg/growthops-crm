from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
flush_block = """  async function flushSave(){
    if(hydrating||suppressPersist)return true;
    clearTimeout(saveTimer);saveTimer=null;
    return enqueueSave(false);
  }"""
if adapter.count(flush_block) != 1:
    fail(f'shared flushSave anchor expected once, found {adapter.count(flush_block)}')
if 'vm.persistRestoreDismissedAlertsBarrier=' in adapter:
    fail('restore dismissed alerts durability barrier already present')
adapter = adapter.replace(
    flush_block,
    flush_block + "\n  vm.persistRestoreDismissedAlertsBarrier=()=>flushSave();",
    1,
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacement = """restoreDismissedAlerts(){const collectActiveKeys=()=>{const keys=new Set();this.clients.filter(c=>!c.archived).forEach(c=>{const cs=this.contractDueReminderStage(c,c.endDate);if(c.endDate&&cs)keys.add(`CONTRACT-${c.id}|${c.endDate}|${cs.reminderIndex}`);(c.networkEnvironments||[]).forEach(env=>{const s=this.autoDueReminderStage(env.ipDueDate);if(env.ipDueDate&&s)keys.add(`IP-${c.id}-${env.id}|${env.ipDueDate}|${s.reminderIndex}`)})});this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{const stage=this.autoDueReminderStage(r.dueDate);if(stage)keys.add(`RECEIVABLE-${r.id}|${r.dueDate}|${stage.reminderIndex}`)});return keys},initialActiveKeys=collectActiveKeys(),initialRestoreKeys=new Set((this.dismissedAlerts||[]).map(x=>String(x.key)).filter(key=>initialActiveKeys.has(key))),count=(this.dismissedAlerts||[]).filter(x=>initialRestoreKeys.has(String(x.key))).length;if(!count)return;this.askConfirm({title:'恢复已忽略提醒',message:`将恢复当前阶段的 ${count} 条已忽略提醒，不会修改原始到期日期或应收账单。`,confirmText:'恢复提醒',tone:'warning'},()=>{const liveActiveKeys=collectActiveKeys(),restoreKeys=new Set([...initialRestoreKeys].filter(key=>liveActiveKeys.has(key)));if(!restoreKeys.size){this.notify('提醒状态已变化，请重新操作');return}const before=this.dismissedAlerts||[],next=before.filter(x=>!restoreKeys.has(String(x.key))),removedRows=before.filter(x=>restoreKeys.has(String(x.key))),restoredCount=before.length-next.length;if(!restoredCount){this.notify('提醒状态已变化，请重新操作');return}if(typeof this.persistRestoreDismissedAlertsBarrier!=='function'){this.notify('恢复提醒未保存：云端持久化服务不可用');return}const removedSet=new Set(removedRows),removedSpecs=removedRows.map(row=>{const index=before.indexOf(row);let prev=null,nextRow=null;for(let i=index-1;i>=0;i-=1)if(!removedSet.has(before[i])){prev=before[i];break}for(let i=index+1;i<before.length;i+=1)if(!removedSet.has(before[i])){nextRow=before[i];break}return{row,index,key:String(row?.key??''),prev,next:nextRow}}),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),originalPersist=this.persist;this.dismissedAlerts=next;this.logAudit('恢复已忽略提醒',`${restoredCount} 条`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}if(this.dismissedAlerts===next){const authorityKeys=new Set(this.dismissedAlerts.filter(row=>!removedSet.has(row)).map(row=>String(row?.key??'')).filter(Boolean));for(const spec of [...removedSpecs].sort((a,b)=>a.index-b.index)){if(this.dismissedAlerts.includes(spec.row))continue;if(spec.key&&authorityKeys.has(spec.key))continue;let at=-1;if(spec.next&&this.dismissedAlerts.includes(spec.next))at=this.dismissedAlerts.indexOf(spec.next);else if(spec.prev&&this.dismissedAlerts.includes(spec.prev))at=this.dismissedAlerts.indexOf(spec.prev)+1;else at=Math.max(0,Math.min(spec.index,this.dismissedAlerts.length));this.dismissedAlerts.splice(at,0,spec.row)}}};let barrierResult;try{barrierResult=this.persistRestoreDismissedAlertsBarrier()}catch(e){rollback();originalPersist.call(this);this.notify(`恢复提醒未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`);return}return Promise.resolve(barrierResult).then(()=>{this.notify(`已恢复 ${restoredCount} 条提醒`)},e=>{rollback();originalPersist.call(this);this.notify(`恢复提醒未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}"""

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'restoreDismissedAlerts')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    required = (
        'const collectActiveKeys=()=>',
        'initialRestoreKeys=new Set',
        'this.contractDueReminderStage(c,c.endDate)',
        'this.dismissedAlerts=next',
        'this.persist()',
        "this.logAudit('恢复已忽略提醒'",
        'initialRestoreKeys].filter(key=>liveActiveKeys.has(key))',
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('restoreDismissedAlerts reviewed integrity source drifted: ' + ', '.join(missing))
    if 'persistRestoreDismissedAlertsBarrier' in source:
        fail('restoreDismissedAlerts already ACK-aware')
    patched = text[:start] + replacement + text[end:]
    if patched == text:
        fail('restoreDismissedAlerts ACK replacement made no change')
    path.write_text(patched, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(patched.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'restoreDismissedAlerts expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'DISMISSED_ALERT_RESTORE_PERSISTENCE_ACK_FINALIZE_OK: '
    'restore=initial-confirmed-intersect-live-active+single-cloud-ack-before-success; '
    'failure=attempt-removed-rows+attempt-audit-rollback+rollback-persisted; '
    'concurrency=unrelated-row+same-key-replacement+whole-array-authority-preserved; '
    'missing-barrier=fail-closed+zero-legacy-persist; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
