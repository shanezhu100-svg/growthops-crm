from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('DISMISSED_ALERT_RESTORE_INTEGRITY_FINALIZE_FAILED: ' + message)


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


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacement = """restoreDismissedAlerts(){const collectActiveKeys=()=>{const keys=new Set();this.clients.filter(c=>!c.archived).forEach(c=>{const cs=this.autoDueReminderStage(c.endDate);if(c.endDate&&cs)keys.add(`CONTRACT-${c.id}|${c.endDate}|${cs.reminderIndex}`);(c.networkEnvironments||[]).forEach(env=>{const s=this.autoDueReminderStage(env.ipDueDate);if(env.ipDueDate&&s)keys.add(`IP-${c.id}-${env.id}|${env.ipDueDate}|${s.reminderIndex}`)})});this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{const stage=this.autoDueReminderStage(r.dueDate);if(stage)keys.add(`RECEIVABLE-${r.id}|${r.dueDate}|${stage.reminderIndex}`)});return keys},initialActiveKeys=collectActiveKeys(),initialRestoreKeys=new Set((this.dismissedAlerts||[]).map(x=>String(x.key)).filter(key=>initialActiveKeys.has(key))),count=(this.dismissedAlerts||[]).filter(x=>initialRestoreKeys.has(String(x.key))).length;if(!count)return;this.askConfirm({title:'恢复已忽略提醒',message:`将恢复当前阶段的 ${count} 条已忽略提醒，不会修改原始到期日期或应收账单。`,confirmText:'恢复提醒',tone:'warning'},()=>{const liveActiveKeys=collectActiveKeys(),restoreKeys=new Set([...initialRestoreKeys].filter(key=>liveActiveKeys.has(key)));if(!restoreKeys.size){this.notify('提醒状态已变化，请重新操作');return}const before=this.dismissedAlerts||[],next=before.filter(x=>!restoreKeys.has(String(x.key))),restoredCount=before.length-next.length;if(!restoredCount){this.notify('提醒状态已变化，请重新操作');return}this.dismissedAlerts=next;this.persist();this.logAudit('恢复已忽略提醒',`${restoredCount} 条`);this.notify(`已恢复 ${restoredCount} 条提醒`)})}"""

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
        'const activeKeys=new Set()',
        'this.clients.filter(c=>!c.archived)',
        'this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate)',
        "title:'恢复已忽略提醒'",
        'this.dismissedAlerts=(this.dismissedAlerts||[]).filter',
        "this.logAudit('恢复已忽略提醒',`${count} 条`)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('restoreDismissedAlerts reviewed source drifted: ' + ', '.join(missing))
    patched = text[:start] + replacement + text[end:]
    if patched == text:
        fail('restoreDismissedAlerts replacement made no change')
    path.write_text(patched, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(patched.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'restoreDismissedAlerts expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'DISMISSED_ALERT_RESTORE_INTEGRITY_FINALIZE_OK: '
    'initial-confirm-set=locked; confirm-time-active-state=recomputed; '
    'restore=initial-confirmed-intersect-live-active; newly-active=excluded; '
    'fully-stale=denied-before-persist+audit; audit-count=actual-restored; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
