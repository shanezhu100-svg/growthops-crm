from pathlib import Path
import hashlib, json, re, shutil

root = Path(__file__).resolve().parent
srcdir = root / '.final-page-canonical'
TARGET_BYTES = 643031
TARGET_SHA256 = '51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43'
pat = re.compile(r'offset-(\d+)-(\d+)\.htmlpart$')

parts = []
for p in srcdir.iterdir():
    m = pat.fullmatch(p.name)
    if not m:
        continue
    start, end = map(int, m.groups())
    raw = p.read_bytes()
    if end <= start or len(raw) != end - start:
        raise SystemExit(f'Invalid canonical chunk: {p.name}')
    parts.append((start, end, p, raw))

parts.sort(key=lambda x: (x[0], x[1]))
pos = 0
raw = bytearray()
for start, end, p, chunk in parts:
    if start != pos:
        kind = 'overlap' if start < pos else 'gap'
        raise SystemExit(f'Canonical source {kind}: expected {pos}, got {start} ({p.name})')
    raw.extend(chunk)
    pos = end

if pos != TARGET_BYTES:
    raise SystemExit(f'Canonical source incomplete: {pos} != {TARGET_BYTES}')
digest = hashlib.sha256(raw).hexdigest()
if digest != TARGET_SHA256:
    raise SystemExit(f'Canonical source SHA mismatch: {digest} != {TARGET_SHA256}')

html = bytes(raw).decode('utf-8')
legacy = (root / 'index.html').read_text(encoding='utf-8')
url = re.search(r"const SUPABASE_URL='([^']+)'", legacy)
key = re.search(r"const API_KEY='([^']+)'", legacy)
if not url or not key:
    raise SystemExit('Existing browser-safe Supabase config not found')

if html.count('createApp({') != 1:
    raise SystemExit('Unexpected Vue app bootstrap count')
html = html.replace('createApp({', 'window.__growthOpsVm=createApp({', 1)

# Remove the small pointer icons from the four lead summary cards while
# preserving the cards' click/filter behavior and all other layout/content.
lead_pointer_icons = (
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-slate-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-amber-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-cyan-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-emerald-300"></i>',
)
for icon in lead_pointer_icons:
    if html.count(icon) != 1:
        raise SystemExit(f'Unexpected lead pointer icon count: {icon}')
    html = html.replace(icon, '', 1)

start = html.index('\n  mounted(){')
end = html.index("\n}).mount('#app');", start)
html = html[:start] + '\n  mounted(){}' + html[end:]

config = (
    '<script>'
    f'window.__GROWTHOPS_SUPABASE_URL__={json.dumps(url.group(1))};'
    f'window.__GROWTHOPS_SUPABASE_KEY__={json.dumps(key.group(1))};'
    '</script>'
)
if html.count('</body>') != 1:
    raise SystemExit('Unexpected HTML body ending')
html = html.replace(
    '</body>',
    config + '<script src="/cloud-adapter.js"></script></body>',
    1
)

out = root / 'dist'
if out.exists():
    shutil.rmtree(out)
out.mkdir()
(out / 'index.html').write_text(html, encoding='utf-8')
(out / 'cloud-adapter.js').write_bytes((root / 'cloud-adapter.js').read_bytes())
print(f'Built verified CRM source: {TARGET_BYTES} bytes / {digest}')
