from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('SOP_MUTATION_INTEGRITY_FINALIZE_FAILED: ' + message)


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


def replace_method(text: str, name: str, patcher):
    bounds = method_bounds(text, name)
    if bounds is None:
        return text, False
    start, end = bounds
    source = text[start:end]
    patched = patcher(source)
    if patched == source:
        fail(f'{name} patch made no change')
    return text[:start] + patched + text[end:], True


def patch_save_sop_task(source: str) -> str:
    old = (
        "if(this.sopTaskForm.id){const originalDate=this.sopTaskForm.originalDate||this.selectedSopDate||date;"
        "const originalTasks=this.ensureSopDailyTasks(originalDate);"
        "const originalIndex=originalTasks.findIndex(step=>step.id===this.sopTaskForm.id);"
        "if(originalIndex!==-1)originalTasks.splice(originalIndex,1);"
    )
    new = (
        "if(this.sopTaskForm.id){const originalDate=this.sopTaskForm.originalDate||this.selectedSopDate||date;"
        "const originalTasks=Array.isArray(cfg.dailyTasks?.[originalDate])?cfg.dailyTasks[originalDate]:null;"
        "if(!originalTasks){this.notify('该 SOP 任务已不存在，请刷新页面后重试');return}"
        "const originalIndex=originalTasks.findIndex(step=>String(step.id)===String(this.sopTaskForm.id));"
        "if(originalIndex===-1){this.notify('该 SOP 任务已不存在，请刷新页面后重试');return}"
        "originalTasks.splice(originalIndex,1);"
    )
    if source.count(old) != 1:
        fail(f'saveSopTask stale-edit anchor count={source.count(old)}')
    return source.replace(old, new, 1)


def patch_remove_sop_step(source: str) -> str:
    head_old = (
        "const step=tasks[index],date=this.selectedSopDate,clientName=this.selectedSopClient?.name||'当前客户',"
        "accountName=this.selectedSopAccount?.account?.accountName||this.selectedSopAccount?.account?.adAccountId||'当前账号';"
        "this.askConfirm("
    )
    head_new = (
        "const step=tasks[index],date=this.selectedSopDate,clientId=this.selectedSopClient?.id,"
        "accountKey=this.selectedSopAccountKey,stepId=step.id,clientName=this.selectedSopClient?.name||'当前客户',"
        "accountName=this.selectedSopAccount?.account?.accountName||this.selectedSopAccount?.account?.adAccountId||'当前账号';"
        "this.askConfirm("
    )
    if source.count(head_old) != 1:
        fail(f'removeSopStep identity head anchor count={source.count(head_old)}')
    source = source.replace(head_old, head_new, 1)

    callback_old = (
        "confirmText:'确认删除',tone:'danger'},()=>{delete this.sopChecked[step.id];"
        "delete this.sopExpandedTasks[step.id];tasks.splice(index,1);this.saveSopProgress();this.saveSopDailyTasks();"
        "this.logAudit('删除 SOP 任务',`${clientName} · ${accountName} · ${date} · ${step.text||''}`);"
        "this.notify('任务已删除')})}"
    )
    callback_new = (
        "confirmText:'确认删除',tone:'danger'},()=>{"
        "if(String(this.selectedSopClient?.id)!==String(clientId)||String(this.selectedSopAccountKey)!==String(accountKey)||this.selectedSopDate!==date){"
        "this.notify('SOP 上下文已变化，请重新操作');return}"
        "const liveCfg=this.ensureSelectedSopConfig(),liveTasks=liveCfg&&Array.isArray(liveCfg.dailyTasks?.[date])?liveCfg.dailyTasks[date]:null,"
        "liveIndex=liveTasks?(stepId!=null?liveTasks.findIndex(item=>String(item.id)===String(stepId)):liveTasks.indexOf(step)):-1;"
        "if(liveIndex<0){this.notify('该 SOP 任务已不存在，请刷新页面后重试');return}"
        "const liveStep=liveTasks[liveIndex];delete this.sopChecked[liveStep.id];delete this.sopExpandedTasks[liveStep.id];"
        "liveTasks.splice(liveIndex,1);this.saveSopProgress();this.saveSopDailyTasks();"
        "this.logAudit('删除 SOP 任务',`${clientName} · ${accountName} · ${date} · ${liveStep.text||''}`);"
        "this.notify('任务已删除')})}"
    )
    if source.count(callback_old) != 1:
        fail(f'removeSopStep confirmation callback anchor count={source.count(callback_old)}')
    return source.replace(callback_old, callback_new, 1)


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = {'saveSopTask': 0, 'removeSopStep': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    text, did_save = replace_method(text, 'saveSopTask', patch_save_sop_task)
    if did_save:
        found['saveSopTask'] += 1
    text, did_remove = replace_method(text, 'removeSopStep', patch_remove_sop_step)
    if did_remove:
        found['removeSopStep'] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'SOP_MUTATION_INTEGRITY_FINALIZE_OK: '
    'task-edit=existing-id-required-before-daily-init+persist+audit; '
    'task-delete=context-bound+live-id-recheck-on-confirm; '
    'reorder=delete-original-id; stale=denied-before-progress+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
