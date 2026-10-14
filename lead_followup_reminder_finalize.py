from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('LEAD_FOLLOWUP_REMINDER_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} expected exactly once, found {count}')
    return text.replace(old, new, 1)


def scan_balanced(text: str, start: int, open_char: str, close_char: str, label: str) -> int:
    if start < 0 or start >= len(text) or text[start] != open_char:
        fail(f'{label} expected {open_char}')
    depth = 0
    quote = ''
    escaped = False
    line_comment = False
    block_comment = False
    i = start
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
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    fail(f'{label} unmatched {open_char}')


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)})\s*\([^)]*\)\s*\{{', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    paren = text.find('(', start + len(name))
    paren_end = scan_balanced(text, paren, '(', ')', f'{name} parameters')
    open_pos = paren_end + 1
    while open_pos < len(text) and text[open_pos].isspace():
        open_pos += 1
    if open_pos >= len(text) or text[open_pos] != '{':
        fail(f'{name} body opening brace missing')
    body_end = scan_balanced(text, open_pos, '{', '}', f'{name} body')
    return start, body_end + 1


def patch_method(text: str, name: str, patcher):
    bounds = method_bounds(text, name)
    if bounds is None:
        fail(f'{name} not found')
    start, end = bounds
    source = text[start:end]
    updated = patcher(source)
    if updated == source:
        fail(f'{name} patch made no change')
    return text[:start] + updated + text[end:]


if not INDEX.is_file():
    fail('dist/index.html missing')

# Runs after collection_plan_ui_finalize.py (which also chains the contract
# reminder finalizer) and before inline-script extraction / Vue precompilation.
# Patch the template and the original alertList source once; later receivable
# collection-node wrapping will rename this alertList to _legacyAlertList and
# preserve the lead reminder logic.
html = INDEX.read_text(encoding='utf-8')

alerts_start = html.find('<!-- Alerts -->')
alerts_end = html.find('<!-- Assets -->', alerts_start)
if alerts_start < 0 or alerts_end <= alerts_start:
    fail('alerts template section not found')
alerts = html[alerts_start:alerts_end]

alerts = replace_once(
    alerts,
    '统一汇总合同、IP、收入应收回款与广告账户低余额提醒，并支持独立添加提醒。',
    '统一汇总潜在客户跟进、合同、IP、收入应收回款与广告账户低余额提醒，并支持独立添加提醒。',
    'alerts intro copy',
)
alerts = replace_once(
    alerts,
    "{{ item.typeKey==='AD_RECHARGE' ? (item.balanceStage==='CRITICAL' ? '再次提醒 · ≤ $30' : '首次提醒 · ≤ $100') : daysLeftLabel(item.daysLeft) }}",
    "{{ item.typeKey==='AD_RECHARGE' ? (item.balanceStage==='CRITICAL' ? '再次提醒 · ≤ $30' : '首次提醒 · ≤ $100') : item.typeKey==='LEAD_FOLLOWUP' ? followupLabel(item.dueDate) : daysLeftLabel(item.daysLeft) }}",
    'lead timing badge',
)
alerts = replace_once(
    alerts,
    '<span class="text-slate-400">到期日期</span>',
    '<span class="text-slate-400">到期 / 跟进日期</span>',
    'lead date label',
)
alerts = replace_once(
    alerts,
    '<span class="text-slate-400">费用</span>',
    '<span class="text-slate-400">费用 / 阶段 / 负责人</span>',
    'lead detail label',
)
alerts = replace_once(
    alerts,
    "{{ item.typeKey==='CONTRACT' ? '产品 / 服务' : item.typeKey==='RECEIVABLE' ? '账单 / 已收' : '环境 / 平台' }}",
    "{{ item.typeKey==='LEAD_FOLLOWUP' ? '联系人' : item.typeKey==='CONTRACT' ? '产品 / 服务' : item.typeKey==='RECEIVABLE' ? '账单 / 已收' : '环境 / 平台' }}",
    'lead target label',
)
alerts = replace_once(
    alerts,
    "{{ item.typeKey==='AD_RECHARGE'?'登记充值':item.typeKey==='RECEIVABLE'?'登记回款':'完成续费' }}",
    "{{ item.typeKey==='AD_RECHARGE'?'登记充值':item.typeKey==='RECEIVABLE'?'登记回款':item.typeKey==='LEAD_FOLLOWUP'?'查看潜客':'完成续费' }}",
    'lead primary action label',
)
html = html[:alerts_start] + alerts + html[alerts_end:]

# Lead reminder timing: enter the window at T-3, escalate at T-1 and T0. The
# T0 stage remains active while overdue until nextFollowUp changes or the lead
# leaves the active pipeline.
auto_bounds = method_bounds(html, 'autoDueReminderStage')
if auto_bounds is None:
    fail('autoDueReminderStage not found')
_, auto_end = auto_bounds
lead_stage_method = (
    "leadFollowupReminderStage(date){if(!date)return null;const days=this.daysUntil(date);"
    "if(days>3)return null;let index=1,daysBefore=3;"
    "if(days<=1){index=2;daysBefore=1}if(days<=0){index=3;daysBefore=0}"
    "return{reminderIndex:index,reminderTotal:3,reminderDaysBefore:daysBefore,"
    "reminderDate:this.addDays(date,-daysBefore)}}"
)
if 'leadFollowupReminderStage(date)' in html:
    fail('leadFollowupReminderStage already exists')
html = html[:auto_end] + ',\n    ' + lead_stage_method + html[auto_end:]


def patch_alert_list(source: str) -> str:
    anchor = '});this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0).forEach(r=>{'
    if source.count(anchor) != 1:
        fail(f'alertList lead insertion anchor count={source.count(anchor)}')
    lead_loop = (
        "});(Array.isArray(this.leads)?this.leads:[]).filter(lead=>lead&&lead.nextFollowUp&&!lead.convertedClientId"
        "&&!['WON','LOST'].includes(lead.stage)).forEach(lead=>{"
        "const stage=this.leadFollowupReminderStage(lead.nextFollowUp);if(!stage)return;"
        "const days=this.daysUntil(lead.nextFollowUp),owner=String(lead.owner||'').trim(),"
        "contact=[lead.contact,lead.contactInfo].filter(Boolean).join(' · ')||'未填写联系人';"
        "list.push({id:`LEAD_FOLLOWUP-${lead.id}`,typeKey:'LEAD_FOLLOWUP',leadId:lead.id,"
        "clientName:lead.company||'未命名潜客',type:'潜客跟进',dueDate:lead.nextFollowUp,"
        "daysLeft:days,cost:`${this.leadStageText(lead.stage)}${owner?` · ${owner}`:''}`,"
        "target:contact,isStandalone:false,...stage})});"
        "this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0).forEach(r=>{"
    )
    return source.replace(anchor, lead_loop, 1)


html = patch_method(html, 'alertList', patch_alert_list)


def patch_alert_filters(source: str) -> str:
    anchor = "{key:'ALL',label:'全部',count:this.alertList.length},"
    addition = anchor + "{key:'LEAD_FOLLOWUP',label:'潜客跟进',count:cnt('LEAD_FOLLOWUP')},"
    if source.count(anchor) != 1:
        fail(f'alertFilters anchor count={source.count(anchor)}')
    return source.replace(anchor, addition, 1)


html = patch_method(html, 'alertFilters', patch_alert_filters)


def patch_active_dismissed(source: str) -> str:
    anchor = '});this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{'
    if source.count(anchor) != 1:
        fail(f'activeDismissedAlertCount anchor count={source.count(anchor)}')
    lead_keys = (
        "});(Array.isArray(this.leads)?this.leads:[]).filter(lead=>lead&&lead.nextFollowUp&&!lead.convertedClientId"
        "&&!['WON','LOST'].includes(lead.stage)).forEach(lead=>{"
        "const stage=this.leadFollowupReminderStage(lead.nextFollowUp);"
        "if(stage)keys.add(`LEAD_FOLLOWUP-${lead.id}|${lead.nextFollowUp}|${stage.reminderIndex}`)});"
        "this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{"
    )
    return source.replace(anchor, lead_keys, 1)


html = patch_method(html, 'activeDismissedAlertCount', patch_active_dismissed)


def patch_dashboard_cards(source: str) -> str:
    old = "hint:'合同 / IP / 应收回款 / 广告余额'"
    new = "hint:'潜客跟进 / 合同 / IP / 应收 / 广告余额'"
    if source.count(old) != 1:
        fail(f'dashboard reminder hint count={source.count(old)}')
    return source.replace(old, new, 1)


html = patch_method(html, 'dashboardCards', patch_dashboard_cards)


def patch_alert_type_name(source: str) -> str:
    old = "alertTypeName(k){if(k==='AD_RECHARGE')"
    new = "alertTypeName(k){if(k==='LEAD_FOLLOWUP')return'潜客跟进提醒';if(k==='AD_RECHARGE')"
    if source.count(old) != 1:
        fail('alertTypeName source drifted')
    return source.replace(old, new, 1)


html = patch_method(html, 'alertTypeName', patch_alert_type_name)


def patch_alert_style(source: str) -> str:
    old = "alertStyle(k){if(k==='CONTRACT')"
    new = "alertStyle(k){if(k==='LEAD_FOLLOWUP')return{bg:'bg-violet-50',text:'text-violet-600',icon:'fa-solid fa-user-clock'};if(k==='CONTRACT')"
    if source.count(old) != 1:
        fail('alertStyle source drifted')
    return source.replace(old, new, 1)


html = patch_method(html, 'alertStyle', patch_alert_style)


def patch_ignore_followup(source: str) -> str:
    anchor = "const idx=Number(item?.reminderIndex||0),total=Number(item?.reminderTotal||3);"
    if source.count(anchor) != 1:
        fail('alertIgnoreFollowupText source drifted')
    lead_copy = (
        anchor
        + "if(item?.typeKey==='LEAD_FOLLOWUP'){"
        + "if(idx<=1)return'仅忽略当前提前跟进阶段；进入跟进前 1 天和当天 / 逾期阶段时会再次提醒。';"
        + "if(idx===2)return'仅忽略当前阶段；到跟进当天或逾期后会再次提醒。';"
        + "return'将忽略当前跟进日期的当天 / 逾期提醒；修改下次跟进日期后，新一轮会重新提醒。'}"
    )
    return source.replace(anchor, lead_copy, 1)


html = patch_method(html, 'alertIgnoreFollowupText', patch_ignore_followup)


def patch_restore_dismissed(source: str) -> str:
    anchor = '});this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{'
    if source.count(anchor) != 1:
        fail(f'restoreDismissedAlerts lead anchor count={source.count(anchor)}')
    lead_keys = (
        "});(Array.isArray(this.leads)?this.leads:[]).filter(lead=>lead&&lead.nextFollowUp&&!lead.convertedClientId"
        "&&!['WON','LOST'].includes(lead.stage)).forEach(lead=>{"
        "const stage=this.leadFollowupReminderStage(lead.nextFollowUp);"
        "if(stage)keys.add(`LEAD_FOLLOWUP-${lead.id}|${lead.nextFollowUp}|${stage.reminderIndex}`)});"
        "this.financeReceivables.filter(r=>this.financeReceivableUnpaid(r)>0&&r.dueDate).forEach(r=>{"
    )
    updated = source.replace(anchor, lead_keys, 1)
    if '不会修改原始到期日期或应收账单。' not in updated:
        fail('restoreDismissedAlerts copy anchor missing')
    return updated.replace(
        '不会修改原始到期日期或应收账单。',
        '不会修改原始跟进 / 到期日期或应收账单。',
        1,
    )


html = patch_method(html, 'restoreDismissedAlerts', patch_restore_dismissed)


def patch_handle_complete(source: str) -> str:
    anchor = "handleAlertComplete(item){if(item.typeKey==='AD_RECHARGE')"
    if source.count(anchor) != 1:
        fail('handleAlertComplete source drifted')
    lead_action = (
        "handleAlertComplete(item){if(item.typeKey==='LEAD_FOLLOWUP'){"
        "const lead=(Array.isArray(this.leads)?this.leads:[]).find(lead=>String(lead.id)===String(item.leadId));"
        "if(!lead){this.notify('潜在客户已不存在或已删除');return}"
        "this.leadPoolFilter='ACTIVE';this.leadQuickFilter='ALL';this.navigateTo('leads');"
        "this.$nextTick(()=>this.openLeadModal(lead));return}"
        "if(item.typeKey==='AD_RECHARGE')"
    )
    return source.replace(anchor, lead_action, 1)


html = patch_method(html, 'handleAlertComplete', patch_handle_complete)


def patch_notice_text(source: str) -> str:
    anchor = "noticeText(item){if(item.typeKey==='AD_RECHARGE')"
    if source.count(anchor) != 1:
        fail('noticeText source drifted')
    lead_notice = (
        "noticeText(item){if(item.typeKey==='LEAD_FOLLOWUP')"
        "return`【潜客跟进提醒】${item.clientName} 计划于 ${item.dueDate} 跟进（${this.followupLabel(item.dueDate)}）。"
        "${item.cost?`阶段 / 负责人：${item.cost}。`:''}${item.target?`联系人：${item.target}。`:''}"
        "请及时跟进并更新下一次跟进日期。`;"
        "if(item.typeKey==='AD_RECHARGE')"
    )
    return source.replace(anchor, lead_notice, 1)


html = patch_method(html, 'noticeText', patch_notice_text)

INDEX.write_text(html, encoding='utf-8')
sha = hashlib.sha256(html.encode('utf-8')).hexdigest()
print(
    'LEAD_FOLLOWUP_REMINDER_FINALIZE_OK: '
    'window=3d+1d+today+overdue-continuous; active-stages=NEW+CONTACTED+QUALIFIED+PROPOSAL; '
    'won+lost+converted=excluded; dismissal=stage-aware+restorable; action=opens-lead; '
    'copy=followup-semantic; '
    f'index={sha[:12]}'
)

import test_lead_followup_reminder_output  # noqa: E402,F401
