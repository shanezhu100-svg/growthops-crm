from pathlib import Path
import hashlib, shutil

root=Path(__file__).resolve().parent
dist=root/'dist'
index_path=dist/'index.html'
src=root/'cloud-ui-action-bridge.js'
dst=dist/'cloud-ui-action-bridge.js'
anchor_src=root/'client-scroll-anchor-bridge.js'
anchor_dst=dist/'client-scroll-anchor-bridge.js'

if not index_path.exists(): raise SystemExit('dist/index.html missing')
if not src.exists(): raise SystemExit('cloud-ui-action-bridge.js missing')
if not anchor_src.exists(): raise SystemExit('client-scroll-anchor-bridge.js missing')
html=index_path.read_text(encoding='utf-8')
security_tag='<script src="/cloud-security-hotfix.js"></script>'
bridge_tag='<script src="/cloud-ui-action-bridge.js"></script>'
anchor_tag='<script src="/client-scroll-anchor-bridge.js"></script>'
restore_guard='''<style id="growthops-session-restore-style">
html.growthops-session-restoring body>*{visibility:hidden!important}
html.growthops-session-restoring body::before{content:'正在恢复登录会话…';visibility:visible!important;position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:#f8fafc;color:#334155;font:600 14px/1.4 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:.02em}
</style><script id="growthops-session-restore-guard">(()=>{try{if(localStorage.getItem('growthops_crm_token_v2')){document.documentElement.classList.add('growthops-session-restoring');setTimeout(()=>document.documentElement.classList.remove('growthops-session-restoring'),10000)}}catch{}})();</script>'''
if html.count(security_tag)!=1: raise SystemExit('security hotfix tag count mismatch')
if bridge_tag in html: raise SystemExit('UI action bridge already injected')
if anchor_tag in html: raise SystemExit('client scroll anchor bridge already injected')
if 'growthops-session-restore-guard' in html: raise SystemExit('session restore guard already injected')
if '</head>' not in html: raise SystemExit('head close tag missing')
html=html.replace('</head>',restore_guard+'</head>',1)
html=html.replace(security_tag,security_tag+bridge_tag+anchor_tag,1)
index_path.write_text(html,encoding='utf-8')
shutil.copyfile(src,dst)
shutil.copyfile(anchor_src,anchor_dst)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(f'UI_ACTION_FINALIZE_OK: index={sha(index_path)}; bridge={sha(dst)}; anchor={sha(anchor_dst)}')