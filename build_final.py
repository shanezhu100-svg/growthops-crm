from pathlib import Path
import re, json

root=Path(__file__).resolve().parent
srcdir=root/'.final-page-authoritative'
TARGET=510961
EXCLUDED={'offset-500200-516200.htmlpart'}
parts=[]
for p in srcdir.glob('offset-*-*.htmlpart'):
    if p.name in EXCLUDED:
        continue
    m=re.fullmatch(r'offset-(\d+)-(\d+)\.htmlpart',p.name)
    if not m:
        continue
    s,e=map(int,m.groups())
    data=p.read_bytes()
    if 0<=s<e<=TARGET and len(data)==e-s:
        parts.append((s,e,p,data))

by={}
for s,e,p,data in parts:
    by.setdefault(s,[]).append((e,p,data))
for s in by:
    by[s].sort(key=lambda x:x[0],reverse=True)

seen=set()
def walk(pos):
    if pos==TARGET:
        return []
    if pos in seen:
        return None
    seen.add(pos)
    for e,p,data in by.get(pos,[]):
        r=walk(e)
        if r is not None:
            return [(pos,e,p,data)]+r
    return None

chain=walk(0)
if not chain:
    raise SystemExit('No contiguous final-page source chain from 0 to 510961')
raw=b''.join(data for _,_,_,data in chain)
if len(raw)!=TARGET or not raw.endswith(b'</html>\n'):
    raise SystemExit('Final source integrity check failed')

html=raw.decode('utf-8')
legacy=(root/'index.html').read_text(encoding='utf-8')
url=re.search(r"const SUPABASE_URL='([^']+)'",legacy)
key=re.search(r"const API_KEY='([^']+)'",legacy)
if not url or not key:
    raise SystemExit('Existing browser-safe Supabase config not found')

html=html.replace('createApp({','window.__growthOpsVm=createApp({',1)
start=html.index('\n  mounted(){')
end=html.index("\n}).mount('#app');",start)
html=html[:start]+'\n  mounted(){}'+html[end:]
config=(
    '<script>'
    f'window.__GROWTHOPS_SUPABASE_URL__={json.dumps(url.group(1))};'
    f'window.__GROWTHOPS_SUPABASE_KEY__={json.dumps(key.group(1))};'
    '</script>'
)
html=html.replace('</body>',config+'<script src="/cloud-adapter.js"></script></body>',1)

out=root/'dist'
out.mkdir(exist_ok=True)
(out/'index.html').write_text(html,encoding='utf-8')
(out/'cloud-adapter.js').write_bytes((root/'cloud-adapter.js').read_bytes())
