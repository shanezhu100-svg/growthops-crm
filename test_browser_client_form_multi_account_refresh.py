from pathlib import Path
import http.server
import json
import mimetypes
import re
import shutil
import socket
import subprocess
import threading

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
HOTFIX = DIST / 'cloud-security-hotfix.js'


def fail(message: str) -> None:
    raise SystemExit('BROWSER_CLIENT_FORM_MULTI_ACCOUNT_REFRESH_FAILED: ' + message)


if not HOTFIX.is_file():
    fail('dist/cloud-security-hotfix.js missing; run canonical build first')

browser = next(
    (
        shutil.which(name)
        for name in ('google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser')
        if shutil.which(name)
    ),
    None,
)
if not browser:
    fail('no supported Chromium executable on CI runner')

# Synthetic-only fixture for the reported edit/refresh bug. The four mutation inputs
# start blank exactly as they do after a secure reload. Internal account IDs are not
# rendered into the cards. The safe-summary response must still map each saved login
# and saved-password presence back to the correct Facebook/TikTok card. This test does
# not exercise reveal/eye-button behavior; that remains covered by the pre-existing
# client-form credential interaction regression.
fixture = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"><title>multi-account refresh regression</title>
  <link rel="stylesheet" href="/vendor/fontawesome/css/all.min.css">
  <style>
    body{font:14px system-ui,sans-serif;padding:20px}
    .field{width:480px;margin:14px 0}
    .field label{display:block;margin-bottom:6px}
    .field input{display:block;width:100%;height:48px;box-sizing:border-box;padding:0 14px}
    .account-card{padding:12px;margin:12px 0;border:1px solid #ddd}
  </style>
</head>
<body>
  <h1>Synthetic Client</h1>
  <section><h2>Facebook 资产</h2>
    <div class="account-card"><h3>电动叉车</h3><div class="field"><label>登录账号</label><input id="fb1-login" value="" placeholder="邮箱 / 个人号"></div><div class="field"><label>密码 / 2FA</label><input id="fb1-secret" value="" placeholder="密码 / 2FA Token"></div></div>
    <div class="account-card"><h3>工程机械</h3><div class="field"><label>登录账号</label><input id="fb2-login" value="" placeholder="邮箱 / 个人号"></div><div class="field"><label>密码 / 2FA</label><input id="fb2-secret" value="" placeholder="密码 / 2FA Token"></div></div>
  </section>
  <section><h2>TikTok 资产</h2>
    <div class="account-card"><h3>电动叉车</h3><div class="field"><label>登录账号</label><input id="tk1-login" value="" placeholder="邮箱 / TikTok 账号"></div><div class="field"><label>密码 / 2FA</label><input id="tk1-secret" value="" placeholder="密码 / 2FA Token"></div></div>
    <div class="account-card"><h3>工程机械</h3><div class="field"><label>登录账号</label><input id="tk2-login" value="" placeholder="邮箱 / TikTok 账号"></div><div class="field"><label>密码 / 2FA</label><input id="tk2-secret" value="" placeholder="密码 / 2FA Token"></div></div>
  </section>
  <script>
    window.__growthOpsCredentialSummaryCalls=[];
    window.__growthOpsUnexpectedRpc=[];
    window.__growthOpsVm={
      currentPage:'client-form', selectedClientId:'client-1', selectedAssetsClientId:0,
      currentUser:{id:'admin-1',role:'ADMIN'}, clients:[{id:'client-1',name:'Synthetic Client'}],
      selectedClient:{id:'client-1',name:'Synthetic Client',
        fbAccounts:[{id:'fb-internal-1'},{id:'fb-internal-2'}],
        tkAccounts:[{id:'tk-internal-1'},{id:'tk-internal-2'}]},
      notify:()=>{}, persist:()=>{}, updateStorageUsage:()=>{}, logAudit:()=>{}
    };
    window.__growthOpsCloud={rpc:(name,args)=>{
      if(name==='crm_client_account_safe_summary'){
        window.__growthOpsCredentialSummaryCalls.push(args||{});
        return Promise.resolve({
          facebookAccounts:[
            {id:'fb-internal-1',loginAccount:'fb-one@example.test',hasPassword:true,has2FA:true},
            {id:'fb-internal-2',loginAccount:'fb-two@example.test',hasPassword:true,has2FA:false}],
          tiktokAccounts:[
            {id:'tk-internal-1',loginAccount:'tk-one@example.test',hasPassword:true,has2FA:false},
            {id:'tk-internal-2',loginAccount:'tk-two@example.test',hasPassword:true,has2FA:true}],
          facebook:{loginAccount:'legacy-fb-wrong@example.test',hasPassword:false,has2FA:false},
          tiktok:{loginAccount:'legacy-tk-wrong@example.test',hasPassword:false,has2FA:false}
        });
      }
      window.__growthOpsUnexpectedRpc.push(name);
      return Promise.reject(new Error('UNEXPECTED_TEST_RPC'));
    }};
  </script>
  <script src="/cloud-security-hotfix.js"></script>
  <script>
    setTimeout(()=>{
      const accounts=[...document.querySelectorAll('[data-growthops-credential-form-status="account"]')];
      const secrets=[...document.querySelectorAll('[data-growthops-credential-form-status="secret"]')];
      const accountTexts=accounts.map(node=>String(node.textContent||'').trim());
      const secretTexts=secrets.map(node=>String(node.textContent||'').trim());
      const expected=['fb-one@example.test','fb-two@example.test','tk-one@example.test','tk-two@example.test'];
      const inputs=['fb1-login','fb1-secret','fb2-login','fb2-secret','tk1-login','tk1-secret','tk2-login','tk2-secret'].map(id=>document.getElementById(id));
      const inputValues=inputs.map(node=>node?.value??'__missing__');
      const summaries=window.__growthOpsCredentialSummaryCalls||[];
      const unexpected=window.__growthOpsUnexpectedRpc||[];
      const exact=expected.every((value,index)=>accountTexts[index]===value);
      const masked=secretTexts.length===4&&secretTexts.every(text=>text.includes('••••••••'));
      const noLegacy=accountTexts.every(text=>!text.includes('legacy-'));
      const blanks=inputValues.every(value=>value==='');
      const pass=accounts.length===4&&secrets.length===4&&exact&&masked&&noLegacy&&blanks&&summaries.length===1&&String(summaries[0]?.p_client_id||'')==='client-1'&&unexpected.length===0;
      document.body.setAttribute('data-refresh-regression',pass?'pass':'fail');
      document.body.setAttribute('data-account-texts',JSON.stringify(accountTexts));
      document.body.setAttribute('data-secret-texts',JSON.stringify(secretTexts));
      document.body.setAttribute('data-input-values',JSON.stringify(inputValues));
      document.body.setAttribute('data-summary-client-id',String(summaries[0]?.p_client_id||''));
      document.body.setAttribute('data-unexpected-rpc-count',String(unexpected.length));
    },1400);
  </script>
</body></html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404); return
        body=path.read_bytes()
        content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if path.suffix=='.js': content_type='application/javascript; charset=utf-8'
        elif path.suffix=='.css': content_type='text/css; charset=utf-8'
        self.send_response(200); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/','/fixture.html'):
            body=fixture.encode('utf-8'); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path=='/cloud-security-hotfix.js': self.send_file(HOTFIX); return
        if self.path.startswith('/vendor/fontawesome/'):
            target=(DIST/self.path.lstrip('/')).resolve(); root=(DIST/'vendor'/'fontawesome').resolve()
            if target!=root and root not in target.parents: self.send_error(403); return
            self.send_file(target); return
        self.send_error(404)


with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
cmd=[browser,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--disable-default-apps','--disable-extensions','--disable-sync','--metrics-recording-only','--no-first-run','--enable-logging=stderr','--v=0','--virtual-time-budget=5000','--dump-dom',f'http://127.0.0.1:{port}/fixture.html']
try:
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=30,check=False)
finally:
    server.shutdown(); server.server_close()

stderr=re.sub(r'\s+',' ',proc.stderr or '').strip()
if proc.returncode!=0:
    fail(f'Chromium exit={proc.returncode}; stderr={stderr[-1200:]}')
dom=proc.stdout or ''
if 'data-refresh-regression="pass"' not in dom:
    attrs={}
    for name in ('data-refresh-regression','data-account-texts','data-secret-texts','data-input-values','data-summary-client-id','data-unexpected-rpc-count'):
        match=re.search(rf'{re.escape(name)}="([^"]*)"',dom); attrs[name]=match.group(1) if match else '__missing__'
    fail('synthetic multi-account refresh regression failed: '+json.dumps(attrs,ensure_ascii=False)+'; stderr='+stderr[-800:])
for value in ('fb-one@example.test','fb-two@example.test','tk-one@example.test','tk-two@example.test'):
    if value not in dom: fail('saved login missing after refresh: '+value)
if 'legacy-fb-wrong@example.test' in dom or 'legacy-tk-wrong@example.test' in dom:
    fail('legacy platform summary reused across multiple accounts')
if 'data-unexpected-rpc-count="0"' not in dom:
    fail('refresh regression invoked an unexpected sensitive RPC')

print('BROWSER_CLIENT_FORM_MULTI_ACCOUNT_REFRESH_OK: facebook=2+tiktok=2; saved-login=per-account; saved-password=masked-on-4; underlying-mutation-inputs=blank; legacy-summary=not-reused; reveal-rpc=not-called')
