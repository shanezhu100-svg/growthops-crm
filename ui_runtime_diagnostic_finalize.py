from pathlib import Path
import hashlib, shutil

root=Path(__file__).resolve().parent
dist=root/'dist'
index_path=dist/'index.html'
src=root/'ui-runtime-diagnostic.js'
dst=dist/'ui-runtime-diagnostic.js'

html=index_path.read_text(encoding='utf-8')
bridge='<script src="/cloud-ui-action-bridge.js"></script>'
diag='<script src="/ui-runtime-diagnostic.js"></script>'
if html.count(bridge)!=1:
    raise SystemExit(f'Unexpected UI bridge tag count: {html.count(bridge)}')
if diag in html:
    raise SystemExit('Runtime diagnostic already injected')
html=html.replace(bridge,bridge+diag,1)
index_path.write_text(html,encoding='utf-8')
shutil.copyfile(src,dst)
print('UI_RUNTIME_DIAGNOSTIC_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; diag='+hashlib.sha256(dst.read_bytes()).hexdigest())
