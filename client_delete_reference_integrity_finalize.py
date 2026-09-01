from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'

OLD = "this.mediaTools=this.mediaTools.map(t=>({...t,bindings:(t.bindings||[]).filter(b=>String(b.clientId)!==id)}));this.clients=this.clients.filter(c=>String(c.id)!==id);"
NEW = "this.mediaTools=this.mediaTools.map(t=>({...t,bindings:(t.bindings||[]).filter(b=>String(b.clientId)!==id)}));(this.leads||[]).forEach(lead=>{if(String(lead?.convertedClientId||'')===id){lead.convertedClientId=null;lead.convertedAt=''}});try{const sopKeys=[];for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key&&(key.startsWith(`growthOpsSop-${id}-`)||key.startsWith(`sop-${id}-`)))sopKeys.push(key)}sopKeys.forEach(key=>localStorage.removeItem(key))}catch(e){}this.clients=this.clients.filter(c=>String(c.id)!==id);"


def fail(message: str) -> None:
    raise SystemExit('CLIENT_DELETE_REFERENCE_INTEGRITY_FINALIZE_FAILED: ' + message)


if not APP_DIR.is_dir():
    fail('dist/app missing; run the application externalization/runtime build first')

matches = []
for path in sorted(APP_DIR.glob('app-inline-*.js')):
    text = path.read_text(encoding='utf-8')
    count = text.count(OLD)
    if count:
        matches.append((path, text, count))

if len(matches) != 1 or matches[0][2] != 1:
    details = ', '.join(f'{path.name}:{count}' for path, _, count in matches) or 'none'
    fail('expected exactly one deleteClient cleanup anchor in final shipped app; found ' + details)

path, text, _ = matches[0]
if 'growthOpsSop-${id}-' in text or "lead.convertedClientId=null;lead.convertedAt=''" in text:
    fail('deleteClient integrity markers already present before exact patch; review duplicate/ordering drift')

patched = text.replace(OLD, NEW, 1)
path.write_text(patched, encoding='utf-8')

print(
    'CLIENT_DELETE_REFERENCE_INTEGRITY_FINALIZE_OK: '
    f'app={path.name}; lead-link=cleared; sop-modern+legacy=purged; '
    'won-stage=untouched; accounting-delete-blockers=untouched'
)
