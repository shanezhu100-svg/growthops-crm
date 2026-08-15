from pathlib import Path
import hashlib, shutil

root=Path(__file__).resolve().parent
dist=root/'dist'
index_path=dist/'index.html'
src=root/'cloud-ui-action-bridge.js'
dst=dist/'cloud-ui-action-bridge.js'

if not index_path.exists(): raise SystemExit('dist/index.html missing')
if not src.exists(): raise SystemExit('cloud-ui-action-bridge.js missing')
html=index_path.read_text(encoding='utf-8')
security_tag='<script src="/cloud-security-hotfix.js"></script>'
bridge_tag='<script src="/cloud-ui-action-bridge.js"></script>'
if html.count(security_tag)!=1: raise SystemExit('security hotfix tag count mismatch')
if bridge_tag in html: raise SystemExit('UI action bridge already injected')
html=html.replace(security_tag,security_tag+bridge_tag,1)
index_path.write_text(html,encoding='utf-8')
shutil.copyfile(src,dst)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(f'UI_ACTION_FINALIZE_OK: index={sha(index_path)}; bridge={sha(dst)}')
