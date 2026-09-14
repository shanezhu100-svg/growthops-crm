from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('CONTRACT_REMINDER_WINDOW_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} expected exactly once, found {count}')
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


if not INDEX.is_file():
    fail('dist/index.html missing')

# Runs after collection_plan_ui_finalize.py but before inline-script extraction and
# Vue template precompilation, so the form field and application methods share one
# precompiled source of truth.
html = INDEX.read_text(encoding='utf-8')

payment_anchor = '''<form-field label="月结默认到期日"><input v-model.number="form.renewalAlertDay" type="number" min="1" max="31" class="field" /><div class="text-[10px] text-slate-400 mt-1">月结一次时使用；半月收款由节点日期覆盖提醒。</div></form-field>'''
reminder_field = payment_anchor + '''<form-field label="合同续费提前提醒（天）"><input v-model.number="form.contractReminderDays" type="number" min="7" max="180" step="1" class="field" /><div class="text-[10px] text-slate-400 mt-1">进入提前提醒窗口后持续显示；到期前 7 / 3 / 1 天自动升级提醒。</div></form-field>'''
html = replace_once(html, payment_anchor, reminder_field, 'contract reminder form field')

normalize_anchor = "if(!c.ipCurrency)"
normalize_new = (
    "const contractReminderDaysRaw=Number(c.contractReminderDays),"
    "contractReminderDays=Number.isFinite(contractReminderDaysRaw)?Math.min(180,Math.max(7,Math.trunc(contractReminderDaysRaw))):25;"
    "c.contractReminderDays=contractReminderDays;"
    + normalize_anchor
)
html = replace_once(html, normalize_anchor, normalize_new, 'normalizeClient contract reminder days')

default_anchor = "endDate:'',renewalAlertDay:25,status:'ACTIVE'"
default_new = "endDate:'',renewalAlertDay:25,contractReminderDays:25,status:'ACTIVE'"
html = replace_once(html, default_anchor, default_new, 'defaultForm contract reminder days')

push_bounds = method_bounds(html, 'pushDueAlert')
if push_bounds is None:
    fail('pushDueAlert not found')
start, end = push_bounds
push_source = html[start:end]
expected_push = "pushDueAlert(list,c,typeKey,date,type,cost,target,networkId=null){if(!date)return;const days=this.daysUntil(date),stage=this.autoDueReminderStage(date);if(stage)list.push({id:`${typeKey}-${c.id}${networkId?`-${networkId}`:''}`,typeKey,clientId:c.id,networkId,clientName:c.name,type,dueDate:date,daysLeft:days,cost,target,isStandalone:false,...stage})}"
if push_source.strip() != expected_push:
    fail('pushDueAlert reviewed source drifted')
contract_method = "contractDueReminderStage(c,date){if(!date)return null;const raw=Number(c?.contractReminderDays),lead=Number.isFinite(raw)?Math.min(180,Math.max(7,Math.trunc(raw))):25,days=this.daysUntil(date);if(days>lead||days<-30)return null;let index=1,daysBefore=lead;if(days<=7){index=2;daysBefore=7}if(days<=3){index=3;daysBefore=3}if(days<=1){index=4;daysBefore=1}return{reminderIndex:index,reminderTotal:4,reminderDaysBefore:daysBefore,reminderDate:this.addDays(date,-daysBefore),reminderWindowDays:lead}},\n    "
new_push = "pushDueAlert(list,c,typeKey,date,type,cost,target,networkId=null){if(!date)return;const days=this.daysUntil(date),stage=typeKey==='CONTRACT'?this.contractDueReminderStage(c,date):this.autoDueReminderStage(date);if(stage)list.push({id:`${typeKey}-${c.id}${networkId?`-${networkId}`:''}`,typeKey,clientId:c.id,networkId,clientName:c.name,type,dueDate:date,daysLeft:days,cost,target,isStandalone:false,...stage})}"
html = html[:start] + contract_method + new_push + html[end:]

restore_bounds = method_bounds(html, 'restoreDismissedAlerts')
if restore_bounds is None:
    fail('restoreDismissedAlerts not found')
start, end = restore_bounds
restore_source = html[start:end]
restore_old = 'const cs=this.autoDueReminderStage(c.endDate);'
restore_new = 'const cs=this.contractDueReminderStage(c,c.endDate);'
if restore_source.count(restore_old) != 1:
    fail(f'restoreDismissedAlerts contract stage anchor count={restore_source.count(restore_old)}')
restore_source = restore_source.replace(restore_old, restore_new, 1)
html = html[:start] + restore_source + html[end:]

follow_bounds = method_bounds(html, 'alertIgnoreFollowupText')
if follow_bounds is None:
    fail('alertIgnoreFollowupText not found')
start, end = follow_bounds
follow_source = html[start:end]
if "item?.typeKey==='RECEIVABLE'" not in follow_source or 'idx<=1' not in follow_source:
    fail('alertIgnoreFollowupText reviewed source drifted')
follow_new = """alertIgnoreFollowupText(item){const idx=Number(item?.reminderIndex||0),total=Number(item?.reminderTotal||3);if(item?.typeKey==='CONTRACT'&&total===4){if(idx<=1)return'仅忽略当前提前提醒阶段；进入到期前 7 天、3 天和 1 天阶段时会再次提醒。';if(idx===2)return'仅忽略当前阶段；进入到期前 3 天和 1 天阶段时会再次提醒。';if(idx===3)return'仅忽略当前阶段；进入到期前 1 天阶段时会再次提醒。';return'将忽略当前到期周期的最后阶段提醒；完成续费或修改到期日期后，新周期仍会重新提醒。'}if(idx<=1)return'仅忽略当前阶段；进入到期前 3 天和 1 天阶段时会再次提醒。';if(idx===2)return'仅忽略当前阶段；进入到期前 1 天阶段时会再次提醒。';if(item?.typeKey==='RECEIVABLE')return'将忽略当前账单最后阶段提醒；账单完成回款后会自动消失，后续月份的新账单仍会正常提醒。';return'将忽略当前到期周期的最后阶段提醒；如果后续完成续费或修改到期日期，新周期仍会重新提醒。'}"""
html = html[:start] + follow_new + html[end:]

delete_bounds = method_bounds(html, 'deleteAlert')
if delete_bounds is None:
    fail('deleteAlert not found')
start, end = delete_bounds
delete_source = html[start:end]
final_stage_old = 'Number(item?.reminderIndex||0)>=3'
final_stage_new = 'Number(item?.reminderIndex||0)>=Number(item?.reminderTotal||3)'
if delete_source.count(final_stage_old) != 1:
    fail(f'deleteAlert final-stage anchor count={delete_source.count(final_stage_old)}')
delete_source = delete_source.replace(final_stage_old, final_stage_new, 1)
html = html[:start] + delete_source + html[end:]

INDEX.write_text(html, encoding='utf-8')
sha = hashlib.sha256(html.encode('utf-8')).hexdigest()
print(
    'CONTRACT_REMINDER_WINDOW_FINALIZE_OK: '
    'payment-due-day=unchanged+receivable-only; contract-reminder-days=separate+default-25+range-7-180; '
    'contract-window=continuous-from-N-days; escalation=N+7+3+1; ip+receivable=existing-7+3+1; '
    'dismissal=stage-aware+dynamic-final-stage; legacy-client=25-day-default; '
    f'index={sha[:12]}'
)
