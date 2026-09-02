from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_REMINDER_CLOSE_FINALIZE_FAILED: ' + message)


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

old = "this.standaloneAlerts.filter(a=>a.typeKey!=='TOOL').forEach(a=>{const d=this.daysUntil(a.dueDate),stage=this.autoDueReminderStage(a.dueDate);if(stage)list.push({...a,...stage,type:this.alertTypeName(a.typeKey),daysLeft:d,isStandalone:true})})"
new = "this.standaloneAlerts.filter(a=>a.typeKey!=='TOOL').forEach(a=>{if(a.typeKey==='RECEIVABLE'){let linkedRows=[];if(a.receivableId){const linked=this.financeReceivables.find(r=>String(r.id)===String(a.receivableId));if(linked)linkedRows=[linked]}else{let linkedClientId=a.clientId?String(a.clientId):'';if(!linkedClientId&&a.clientName){const matches=this.clients.filter(c=>String(c.name||'').trim()===String(a.clientName||'').trim());if(matches.length===1)linkedClientId=String(matches[0].id)}if(linkedClientId)linkedRows=this.financeReceivables.filter(r=>String(r.clientId)===linkedClientId)}if(linkedRows.length)return}const d=this.daysUntil(a.dueDate),stage=this.autoDueReminderStage(a.dueDate);if(stage)list.push({...a,...stage,type:this.alertTypeName(a.typeKey),daysLeft:d,isStandalone:true})})"

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'alertList')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if source.count(old) != 1:
        fail(f'alertList standalone reminder anchor count={source.count(old)}')
    if 'linkedRows.length' in source:
        fail('alertList already contains receivable linkage guard')
    patched = source.replace(old, new, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'alertList expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'RECEIVABLE_REMINDER_CLOSE_FINALIZE_OK: '
    'automatic-receivable=authoritative; linked-standalone=suppressed; '
    'automatic-outstanding=preserved; unresolved-link=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
