from pathlib import Path
import hashlib

# Keep the already-reviewed durability finalizer intact; this entrypoint executes it
# first, then narrows delete audit rollback to rows created synchronously by the
# confirmed delete action. This prevents unrelated audits appended while cloud ACK is
# pending from being captured by the attempt scope.
import opening_deal_persistence_ack_core  # noqa: F401,E402

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_DEAL_AUDIT_SCOPE_FINALIZE_FAILED: ' + message)


old = "const notices=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};try{await Promise.resolve(action())}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row));const rollback="
new = "const notices=[],attemptAudits=[];this.persist=()=>{persistCalls+=1;return true};this.notify=(...args)=>{notices.push(args)};let actionResult;try{actionResult=action();for(const row of (Array.isArray(this.auditLogs)?this.auditLogs:[]))if(!beforeAudits.has(row))attemptAudits.push(row);await Promise.resolve(actionResult)}finally{this.persist=originalPersist;this.notify=originalNotify}if(!persistCalls){for(const args of notices)originalNotify.apply(this,args);return}const rollback="

if not APP_DIR.is_dir():
    fail('dist/app missing after opening-deal core finalizer')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

matches = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    matches += count
    if count:
        if count != 1:
            fail(f'{path.name} audit-scope anchor expected once, found {count}')
        text = text.replace(old, new, 1)
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if matches != 1 or len(changed) != 1:
    fail(f'reviewed audit-scope anchor expected exactly once across final app, found {matches}')

print(
    'OPENING_DEAL_AUDIT_SCOPE_FINALIZE_OK: '
    'delete-attempt-audit=synchronous-action-object-identity; '
    'ack-wait-unrelated-audits=preserved; durability+rollback=unchanged; '
    f'app={changed[0][0]}:{changed[0][1]}'
)

# Provider create/edit mutates its own source plus denormalized linked opening-deal
# display fields, so its durability barrier must observe the fully finalized deal path.
import opening_provider_persistence_ack_finalize  # noqa: F401,E402
