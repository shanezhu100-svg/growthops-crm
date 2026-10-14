from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('LEAD_FOLLOWUP_REMINDER_OUTPUT_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

required = (
    '统一汇总潜在客户跟进、合同、IP、收入应收回款与广告账户低余额提醒',
    "item.typeKey==='LEAD_FOLLOWUP' ? followupLabel(item.dueDate)",
    '到期 / 跟进日期',
    '费用 / 阶段 / 负责人',
    "item.typeKey==='LEAD_FOLLOWUP' ? '联系人'",
    "item.typeKey==='LEAD_FOLLOWUP'?'查看潜客':'完成续费'",
    "leadFollowupReminderStage(date){if(!date)return null;const days=this.daysUntil(date);if(days>3)return null;",
    "typeKey:'LEAD_FOLLOWUP',leadId:lead.id",
    "!['WON','LOST'].includes(lead.stage)",
    '!lead.convertedClientId',
    "{key:'LEAD_FOLLOWUP',label:'潜客跟进',count:cnt('LEAD_FOLLOWUP')}",
    "if(k==='LEAD_FOLLOWUP')return'潜客跟进提醒'",
    "fa-solid fa-user-clock",
    "item?.typeKey==='LEAD_FOLLOWUP'",
    "handleAlertComplete(item){if(item.typeKey==='LEAD_FOLLOWUP')",
    "noticeText(item){if(item.typeKey==='LEAD_FOLLOWUP')",
    '请及时跟进并更新下一次跟进日期',
    "hint:'潜客跟进 / 合同 / IP / 应收 / 广告余额'",
    "if(quick==='DUE')return !!this.leadFollowupReminderStage(l.nextFollowUp);",
    "due:active.filter(l=>!!this.leadFollowupReminderStage(l.nextFollowUp)).length",
    "days<=3?'text-amber-600':'text-slate-700'",
)
missing = [marker for marker in required if marker not in html]
if missing:
    fail('missing markers: ' + ' | '.join(missing))

key_marker = "keys.add(`LEAD_FOLLOWUP-${lead.id}|${lead.nextFollowUp}|${stage.reminderIndex}`)"
if html.count(key_marker) != 2:
    fail(f'lead dismissal/restore key count drifted: {html.count(key_marker)}')
if html.count("leadFollowupReminderStage(lead.nextFollowUp)") < 3:
    fail('lead stage helper must drive alert generation and dismissed-key authority')

print(
    'LEAD_FOLLOWUP_REMINDER_OUTPUT_OK: '
    'template=filter+lead-labels+open-action; window=3/1/0+overdue; '
    'active-only=won+lost+converted-excluded; dismissal=stage-aware+restorable; '
    'copy=followup-semantic; lead-page=3d-queue+color-coded'
)
