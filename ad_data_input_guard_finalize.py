from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
METHOD = 'saveAdDataRecord'
GUARD_MARKER = 'const adRawNumericFields='


def fail(message: str) -> None:
    raise SystemExit('AD_DATA_INPUT_GUARD_FINALIZE_FAILED: ' + message)


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
    fail('dist/app missing; run final runtime build first')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts found')

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, METHOD)
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end]
    if GUARD_MARKER in source:
        fail(f'{METHOD} already contains ad raw numeric guard')
    anchor = 'if(!client||!account)return;'
    if source.count(anchor) != 1:
        fail(f'{METHOD} expected one client/account anchor, found {source.count(anchor)}')
    guard = (
        "const adRawNumericFields=['spend','impressions','clicks','leads','conversions','revenue'];"
        "if(this.selectedAdsPlatform==='FB')adRawNumericFields.push('reach');"
        "if(adRawNumericFields.some(key=>{const value=this.adDataForm?.[key];"
        "if(value===null||value===undefined||value==='')return false;"
        "const numeric=Number(value);return !Number.isFinite(numeric)||numeric<0}))"
        "{this.notify('请输入有效的广告投放数值');return;}"
    )
    patched = source.replace(anchor, anchor + guard, 1)
    text = text[:start] + patched + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'{METHOD} expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'AD_DATA_INPUT_GUARD_FINALIZE_OK: '
    'common=spend+impressions+clicks+leads+conversions+revenue; fb=reach; '
    'finite-nonnegative=required; empty+zero=preserved; '
    'negative+nan+infinity=denied-before-month-lock+mutation+sync+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
