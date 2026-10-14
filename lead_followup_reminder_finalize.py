from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('LEAD_FOLLOWUP_REMINDER_FINALIZE_FAILED: ' + message)


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
        if ch in ('"', "'", chr(96)):
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

# Lead follow-up remains a potential-customer-page workflow only.
# The reminder center intentionally does not receive LEAD_FOLLOWUP alerts.
html = INDEX.read_text(encoding='utf-8')

# Page timing: enter the lead work queue at T-3, remain visible today/overdue,
# and stop once the lead leaves the active pipeline.
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


def patch_filtered_leads(source: str) -> str:
    old = "if(quick==='DUE')return !!l.nextFollowUp&&String(l.nextFollowUp)<=today;"
    new = "if(quick==='DUE')return !!l.nextFollowUp&&(typeof this.leadFollowupReminderStage==='function'?!!this.leadFollowupReminderStage(l.nextFollowUp):String(l.nextFollowUp)<=today);"
    if source.count(old) != 1:
        fail('filteredLeads DUE rule drifted')
    return source.replace(old, new, 1)


html = patch_method(html, 'filteredLeads', patch_filtered_leads)


def patch_lead_stats(source: str) -> str:
    old = "due:active.filter(l=>l.nextFollowUp&&l.nextFollowUp<=today).length"
    new = "due:active.filter(l=>l.nextFollowUp&&(typeof this.leadFollowupReminderStage==='function'?!!this.leadFollowupReminderStage(l.nextFollowUp):String(l.nextFollowUp)<=today)).length"
    if source.count(old) != 1:
        fail('leadStats due rule drifted')
    return source.replace(old, new, 1)


html = patch_method(html, 'leadStats', patch_lead_stats)


def patch_lead_followup_class(source: str) -> str:
    old = "return this.daysUntil(lead.nextFollowUp)<=0?'text-rose-600':'text-slate-700'"
    new = "const days=this.daysUntil(lead.nextFollowUp);return days<=0?'text-rose-600':days<=3?'text-amber-600':'text-slate-700'"
    if source.count(old) != 1:
        fail('leadFollowupClass rule drifted')
    return source.replace(old, new, 1)


html = patch_method(html, 'leadFollowupClass', patch_lead_followup_class)

INDEX.write_text(html, encoding='utf-8')
sha = hashlib.sha256(html.encode('utf-8')).hexdigest()
print(
    'LEAD_FOLLOWUP_REMINDER_FINALIZE_OK: '
    'surface=lead-page-only; reminder-center=disabled; '
    'window=3d+today+overdue-continuous; active-stages=NEW+CONTACTED+QUALIFIED+PROPOSAL; '
    'won+lost+converted=excluded; lead-page=3d-queue+color-coded; '
    f'index={sha[:12]}'
)

import test_lead_followup_reminder_output  # noqa: E402,F401
