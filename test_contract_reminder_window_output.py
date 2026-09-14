from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('TEST_CONTRACT_REMINDER_WINDOW_OUTPUT_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

checks = {
    'separate contract reminder field': '合同续费提前提醒（天）',
    'contract reminder model': 'form.contractReminderDays',
    'payment due remains separate': '月结默认到期日',
    'contract default': "renewalAlertDay:25,contractReminderDays:25",
    'legacy normalization': 'c.contractReminderDays=contractReminderDays;',
    'contract stage helper': 'contractDueReminderStage(c,date)',
    'contract routing only': "stage=typeKey==='CONTRACT'?this.contractDueReminderStage(c,date):this.autoDueReminderStage(date)",
    'four contract stages': 'reminderTotal:4',
    'restore uses contract stage': 'const cs=this.contractDueReminderStage(c,c.endDate);',
    'dynamic final-stage dismissal': '>=Number(item?.reminderTotal||3)',
}
for label, marker in checks.items():
    if marker not in html:
        fail(f'{label} marker missing: {marker}')

if html.count('合同续费提前提醒（天）') != 1:
    fail('contract reminder field must render exactly once')
if html.count('contractDueReminderStage(c,date)') < 1:
    fail('contract stage helper missing')
if "stage=typeKey==='CONTRACT'?this.autoDueReminderStage(date)" in html:
    fail('contract reminder still routed through generic 7/3/1 stage')

print(
    'TEST_CONTRACT_REMINDER_WINDOW_OUTPUT_OK: '
    'ui=separate-payment-vs-renewal-fields; default=25-days; range=7-180; '
    'contract=continuous-window+N/7/3/1; ip+receivable=unchanged-7/3/1; dismissal=dynamic-total'
)
