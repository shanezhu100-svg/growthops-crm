from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
for marker in ('async function flushSave()', 'vm.persistExportAuditBarrier=async(attemptRows)=>{'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistFinanceMonthLockBarrier=' in adapter:
    fail('finance month lock barrier helper already present')
adapter = replace_once(
    adapter,
    '  vm.persistExportAuditBarrier=async(attemptRows)=>{',
    '  vm.persistFinanceMonthLockBarrier=()=>flushSave();\n  vm.persistExportAuditBarrier=async(attemptRows)=>{',
    'finance month lock barrier helper placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacement = """toggleFinanceMonthLock(monthKey){if(!monthKey)return;if(!this.canManageFinance()){this.notify('当前角色无财务月结权限');return}const own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key),rollbackAudit=rows=>{const rollbackRows=new Set(rows);this.auditLogs=Array.isArray(this.auditLogs)?this.auditLogs.filter(row=>!rollbackRows.has(row)):[]},auditAttempt=(action,target)=>{const before=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);this.logAudit(action,target);return Array.isArray(this.auditLogs)?this.auditLogs.filter(row=>!before.has(row)):[]},rollbackLock=(attemptLock,attemptSnapshot,hadLock,previousLock,hadSnapshot,previousSnapshot)=>{if(this.financeMonthLocks?.[monthKey]===attemptLock){if(hadLock)this.financeMonthLocks[monthKey]=previousLock;else delete this.financeMonthLocks[monthKey]}if(this.financeMonthSnapshots?.[monthKey]===attemptSnapshot){if(hadSnapshot)this.financeMonthSnapshots[monthKey]=previousSnapshot;else delete this.financeMonthSnapshots[monthKey]}},rollbackUnlock=(hadLock,previousLock,hadSnapshot,previousSnapshot)=>{if(!own(this.financeMonthLocks,monthKey)&&hadLock)this.financeMonthLocks[monthKey]=previousLock;if(!own(this.financeMonthSnapshots,monthKey)&&hadSnapshot)this.financeMonthSnapshots[monthKey]=previousSnapshot};const locked=this.isMonthLocked(monthKey);if(locked&&this.currentUser?.role!=='ADMIN'){this.notify('只有管理员可以解除已完成的月结锁定');return}if(locked){this.askConfirm({title:'解除财务月结',message:`确定解除 ${monthKey} 的月结锁定吗？解除后该月广告、渠道返点、应收金额和成本将重新允许修改，月结冻结快照也会失效。`,confirmText:'确认解锁',tone:'warning'},async()=>{if(!this.canManageFinance()){this.notify('当前角色无财务月结权限');return}if(this.currentUser?.role!=='ADMIN'){this.notify('只有管理员可以解除已完成的月结锁定');return}if(!this.isMonthLocked(monthKey)){this.notify('月结状态已变化，请重新操作');return}if(typeof this.persistFinanceMonthLockBarrier!=='function'){this.notify('解锁未执行：云端持久化服务不可用');return}const hadLock=own(this.financeMonthLocks,monthKey),previousLock=this.financeMonthLocks[monthKey],hadSnapshot=own(this.financeMonthSnapshots,monthKey),previousSnapshot=this.financeMonthSnapshots[monthKey];delete this.financeMonthLocks[monthKey];delete this.financeMonthSnapshots[monthKey];const auditRows=auditAttempt('解除财务月结',monthKey);try{await this.persistFinanceMonthLockBarrier();this.notify(`${monthKey} 已解锁`)}catch(e){rollbackAudit(auditRows);rollbackUnlock(hadLock,previousLock,hadSnapshot,previousSnapshot);this.persist();this.notify(`解锁未完成：云端保存失败，已恢复月结锁定：${e?.message||'保存失败'}`)}})}else{this.ensureAutomaticReceivables({silent:true});this.ensureAutomaticAssetCosts({month:monthKey,silent:true});const check=this.runFinanceMonthCheck(monthKey,false);if(check.issues.length){this.notify(`月结检查未通过：${check.issues.join('；')}`);return}this.askConfirm({title:'完成财务月结',message:`${monthKey} 月结检查已通过。确定完成月结吗？系统会冻结该月收入、广告消耗、返点、成本与利润口径；以后仍可按实际到账日期登记跨月回款。`,confirmText:'确认月结',tone:'warning'},async()=>{if(!this.canManageFinance()){this.notify('当前角色无财务月结权限');return}if(this.isMonthLocked(monthKey)){this.notify('月结状态已变化，请重新操作');return}const liveCheck=this.getFinanceMonthCheck(monthKey);if(liveCheck.issues.length){this.notify(`月结检查未通过：${liveCheck.issues.join('；')}`);return}if(typeof this.persistFinanceMonthLockBarrier!=='function'){this.notify('月结未执行：云端持久化服务不可用');return}const hadLock=own(this.financeMonthLocks,monthKey),previousLock=this.financeMonthLocks[monthKey],hadSnapshot=own(this.financeMonthSnapshots,monthKey),previousSnapshot=this.financeMonthSnapshots[monthKey],snapshot=this.buildFinanceMonthSnapshot(monthKey),attemptLock={lockedAt:new Date().toISOString(),lockedBy:this.currentUser?.name||'',snapshotAt:snapshot.createdAt};this.financeMonthSnapshots[monthKey]=snapshot;this.financeMonthLocks[monthKey]=attemptLock;const auditRows=auditAttempt('完成财务月结',`${monthKey} · 已生成冻结快照`);try{await this.persistFinanceMonthLockBarrier();this.notify(`${monthKey} 已完成月结，历史利润口径已冻结`)}catch(e){rollbackAudit(auditRows);rollbackLock(attemptLock,snapshot,hadLock,previousLock,hadSnapshot,previousSnapshot);this.persist();this.notify(`月结未完成：云端保存失败，已恢复未锁定状态：${e?.message||'保存失败'}`)}})}},"""

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'toggleFinanceMonthLock')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    required = (
        "title:'解除财务月结'",
        "title:'完成财务月结'",
        "this.currentUser?.role!=='ADMIN'",
        "const liveCheck=this.getFinanceMonthCheck(monthKey)",
        "delete this.financeMonthLocks[monthKey]",
        "this.logAudit('解除财务月结'",
        "this.logAudit('完成财务月结'",
        "this.notify(`${monthKey} 已解锁`)",
        "this.notify(`${monthKey} 已完成月结，历史利润口径已冻结`)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('toggleFinanceMonthLock reviewed destructive-confirmation source drifted: ' + ', '.join(missing))
    if 'persistFinanceMonthLockBarrier' in source:
        fail('toggleFinanceMonthLock already contains finance month lock barrier')
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'toggleFinanceMonthLock expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'FINANCE_MONTH_LOCK_PERSISTENCE_ACK_FINALIZE_OK: '
    'lock+unlock=confirm-time-authority+live-state+cloud-save-ack-before-success; '
    'failure=month-state+attempt-audit-rollback+unrelated-audit-preserved+rollback-persisted; '
    'concurrency=same-month-identity/absence-guarded; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)

# Reconciliation confirmation/void must run after both the destructive confirmation
# hardening and this month-lock acknowledgement stage, but before business VM gates.
import reconciliation_persistence_ack_finalize  # noqa: E402,F401
