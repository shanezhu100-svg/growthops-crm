from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('LEAD_CLIENT_STALE_EDIT_GUARD_FINALIZE_FAILED: ' + message)


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


def patch_method(source: str, name: str, form_name: str, collection_name: str, message: str) -> str:
    signature = re.match(rf'{re.escape(name)}\([^)]*\)\s*\{{', source)
    if not signature:
        fail(f'{name} signature drifted')
    if message in source or 'staleEditGuard' in source:
        fail(f'{name} already contains stale-edit guard')
    guard = (
        f"const staleEditGuard=this.{form_name}&&this.{form_name}.id&&"
        f"(!Array.isArray(this.{collection_name})||!this.{collection_name}.some(x=>x&&String(x.id)===String(this.{form_name}.id)));"
        f"if(staleEditGuard){{this.notify('{message}');return}}"
    )
    return source[:signature.end()] + guard + source[signature.end():]


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

specs = {
    'saveLead': ('leadForm', 'leads', '线索已不存在，请刷新后重试'),
    'saveClient': ('form', 'clients', '客户已不存在，请刷新后重试'),
}
found = {name: 0 for name in specs}
changed_files = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, (form_name, collection_name, message) in specs.items():
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        found[name] += 1
        start, end = bounds
        source = text[start:end].rstrip()
        patched = patch_method(source, name, form_name, collection_name, message)
        text = text[:start] + patched + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed_files.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if not changed_files:
    fail('no final runtime artifact changed')

print(
    'LEAD_CLIENT_STALE_EDIT_GUARD_FINALIZE_OK: '
    'lead-edit=missing-id-denied-before-persist+audit; '
    'client-edit=missing-id-denied-before-persist+audit+billing+navigation; '
    'new-record-paths=unchanged; form-state=preserved; '
    + 'artifacts=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed_files)
)
