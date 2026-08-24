from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME_ROOTS = (ROOT / 'api', ROOT / 'functions')
ALLOWED = {
    'api/crm.js',
    'functions/api/crm.js',
}
SENSITIVE_MARKERS = (
    'GROWTHOPS_SUPABASE_SECRET_KEY',
    'apikey',
    'sb_secret_',
)

runtime_files = []
for root in RUNTIME_ROOTS:
    if not root.exists():
        raise SystemExit(f'SERVER_IDENTITY_SINK_INVENTORY_FAILED missing runtime root: {root.relative_to(ROOT)}')
    for path in sorted(root.rglob('*')):
        if path.is_file():
            runtime_files.append(path)

relative = {str(path.relative_to(ROOT)).replace('\\', '/') for path in runtime_files}
unexpected_files = sorted(relative - ALLOWED)
if unexpected_files:
    raise SystemExit(
        'SERVER_IDENTITY_SINK_INVENTORY_FAILED unexpected server runtime file(s) require explicit security review: '
        + ', '.join(unexpected_files)
    )
missing = sorted(ALLOWED - relative)
if missing:
    raise SystemExit('SERVER_IDENTITY_SINK_INVENTORY_FAILED expected BFF missing: ' + ', '.join(missing))

for rel in sorted(ALLOWED):
    text = (ROOT / rel).read_text(encoding='utf-8')
    for marker in SENSITIVE_MARKERS:
        if marker not in text:
            raise SystemExit(f'SERVER_IDENTITY_SINK_INVENTORY_FAILED {rel} missing expected server-identity marker: {marker}')
    for marker in (
        'function supabaseOrigin(',
        "host.endsWith('.supabase.co')",
        "parsed.protocol !== 'https:'",
        'parsed.username',
        'parsed.password',
        'parsed.pathname',
        'parsed.search',
        'parsed.hash',
        'SERVER_IDENTITY_NOT_CONFIGURED',
    ):
        compact_equivalent = marker.replace(' !== ', '!==')
        if marker not in text and compact_equivalent not in text:
            raise SystemExit(f'SERVER_IDENTITY_SINK_INVENTORY_FAILED {rel} missing origin fail-closed guard: {marker}')

# The only server-side deployments are these two BFF files. A future endpoint
# must be added to ALLOWED only after its handling of the server secret is reviewed.
print('SERVER_IDENTITY_SINK_INVENTORY_OK: runtime-files=2; server-secret-sinks=2-reviewed; origin-guard=required; new-server-route=fail-closed')
