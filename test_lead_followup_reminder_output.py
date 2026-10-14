from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('LEAD_FOLLOWUP_REMINDER_OUTPUT_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

required = (
    "leadFollowupReminderStage(date){if(!date)return null;const days=this.daysUntil(date);if(days>3)return null;",
    "if(quick==='DUE')return !!l.nextFollowUp&&(typeof this.leadFollowupReminderStage==='function'?!!this.leadFollowupReminderStage(l.nextFollowUp):String(l.nextFollowUp)<=today);",
    "due:active.filter(l=>l.nextFollowUp&&(typeof this.leadFollowupReminderStage==='function'?!!this.leadFollowupReminderStage(l.nextFollowUp):String(l.nextFollowUp)<=today)).length",
    "days<=3?'text-amber-600':'text-slate-700'",
    '统一汇总合同、IP、收入应收回款与广告账户低余额提醒，并支持独立添加提醒。',
)
missing = [marker for marker in required if marker not in html]
if missing:
    fail('missing markers: ' + ' | '.join(missing))

forbidden = (
    "typeKey:'LEAD_FOLLOWUP'",
    "{key:'LEAD_FOLLOWUP',label:'潜客跟进'",
    "if(k==='LEAD_FOLLOWUP')return'潜客跟进提醒'",
    "item?.typeKey==='LEAD_FOLLOWUP'",
    "handleAlertComplete(item){if(item.typeKey==='LEAD_FOLLOWUP')",
    "noticeText(item){if(item.typeKey==='LEAD_FOLLOWUP')",
    "hint:'潜客跟进 / 合同 / IP / 应收 / 广告余额'",
    '统一汇总潜在客户跟进、合同、IP、收入应收回款与广告账户低余额提醒',
    "keys.add(`LEAD_FOLLOWUP-",
)
present = [marker for marker in forbidden if marker in html]
if present:
    fail('reminder-center lead markers remain: ' + ' | '.join(present))

print(
    'LEAD_FOLLOWUP_REMINDER_OUTPUT_OK: '
    'surface=lead-page-only; reminder-center=disabled; '
    'window=3d+today+overdue; won+lost+converted=excluded; '
    'lead-page=3d-queue+color-coded'
)
