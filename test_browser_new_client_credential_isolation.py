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
    raise SystemExit('BROWSER_NEW_CLIENT_CREDENTIAL_ISOLATION_FAILED: ' + message)


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

# Reproduce the reported failure mode: the user previously edited client-old, then
# opens the new-client form. selectedClientId/selectedClient are deliberately stale,
# while form.id is empty. A create form must not request or render any saved credential
# summary from the previous client.
fixture = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"><title>new client credential isolation</title>
  <style>
    body{font:14px system-ui,sans-serif;padding:20px}
    .field{width:480px;margin:14px 0}
    .field label{display:block;margin-bottom:6px}
    .field input{display:block;width:100%;height:48px;box-sizing:border-box;padding:0 14px}
  </style>
</head>
<body>
  <h1>新增客户</h1>
  <section><h2>Facebook 资产</h2>
    <div class="account-card">
      <div class="field"><label>登录账号</label><input id="fb-login" value="" placeholder="邮箱 / 个人号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="fb-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
  </section>
  <section><h2>TikTok 资产</h2>
    <div class="account-card">
      <div class="field"><label>登录账号</label><input id="tk-login" value="" placeholder="邮箱 / TikTok 账号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="tk-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
  </section>
  <script>
    window.__growthOpsCredentialSummaryCalls=[];
    window.__growthOpsUnexpectedRpc=[];
    window.__growthOpsVm={
      currentPage:'client-form',
      // stale state from the previous client is intentional
      selectedClientId:'client-old',
      selectedAssetsClientId:0,
      currentUser:{id:'admin-1',role:'ADMIN'},
      clients:[{id:'client-old',name:'Previous Client'}],
      selectedClient:{
        id:'client-old',name:'Previous Client',
        fbAccounts:[{id:'fb-old'}],tkAccounts:[{id:'tk-old'}]
      },
      currentClient:{id:'client-old',name:'Previous Client'},
      // authoritative create-mode signal
      form:{id:null,name:'',fbAccounts:[{}],tkAccounts:[{}]},
      notify:()=>{},persist:()=>{},updateStorageUsage:()=>{},logAudit:()=>{}
    };
    window.__growthOpsCloud={
      rpc:(name,args)=>{
        if(name==='crm_client_account_safe_summary'){
          window.__growthOpsCredentialSummaryCalls.push(args||{});
          return Promise.resolve({
            facebook:{loginAccount:'previous-fb@example.test',hasPassword:true,has2FA:true},
            tiktok:{loginAccount:'previous-tk@example.test',hasPassword:true,has2FA:true}
          });
        }
        window.__growthOpsUnexpectedRpc.push(name);
        return Promise.reject(new Error('UNEXPECTED_TEST_RPC'));
      }
    };
  </script>
  <script src="/cloud-security-hotfix.js"></script>
  <script>
    setTimeout(()=>{
      const accounts=[...document.querySelectorAll('[data-growthops-credential-form-status="account"]')];
      const secrets=[...document.querySelectorAll('[data-growthops-credential-form-status="secret"]')];
      const accountTexts=accounts.map(node=>String(node.textContent||'').trim());
      const secretTexts=secrets.map(node=>String(node.textContent||'').trim());
      const inputs=['fb-login','fb-secret','tk-login','tk-secret'].map(id=>document.getElementById(id));
      const inputValues=inputs.map(node=>node?.value??'__missing__');
      const placeholders=inputs.map(node=>String(node?.getAttribute('placeholder')||''));
      const summaryCalls=window.__growthOpsCredentialSummaryCalls||[];
      const unexpected=window.__growthOpsUnexpectedRpc||[];
      const leakedText=[...accountTexts,...secretTexts].some(text=>
        text.includes('previous-fb@example.test')||
        text.includes('previous-tk@example.test')||
        text.includes('••••••••')
      );
      const placeholdersPreserved=placeholders.every(Boolean);
      const pass=(
        summaryCalls.length===0 &&
        unexpected.length===0 &&
        !leakedText &&
        inputValues.every(value=>value==='') &&
        placeholdersPreserved
      );
      document.body.setAttribute('data-new-client-isolation',pass?'pass':'fail');
      document.body.setAttribute('data-summary-call-count',String(summaryCalls.length));
      document.body.setAttribute('data-account-texts',JSON.stringify(accountTexts));
      document.body.setAttribute('data-secret-texts',JSON.stringify(secretTexts));
      document.body.setAttribute('data-input-values',JSON.stringify(inputValues));
      document.body.setAttribute('data-placeholders',JSON.stringify(placeholders));
      document.body.setAttribute('data-unexpected-rpc-count',String(unexpected.length));
    },1600);
  </script>
</body></html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if path.suffix == '.js':
            content_type = 'application/javascript; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/fixture.html'):
            body = fixture.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == '/cloud-security-hotfix.js':
            self.send_file(HOTFIX)
            return
        self.send_error(404)


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]

server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
cmd = [
    browser,
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-background-networking',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--metrics-recording-only',
    '--no-first-run',
    '--enable-logging=stderr',
    '--v=0',
    '--virtual-time-budget=4500',
    '--dump-dom',
    f'http://127.0.0.1:{port}/fixture.html',
]

try:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
finally:
    server.shutdown()
    server.server_close()

stderr = re.sub(r'\s+', ' ', proc.stderr or '').strip()
if proc.returncode != 0:
    fail(f'Chromium exit={proc.returncode}; stderr={stderr[-1600:]}')

dom = proc.stdout or ''
if 'data-new-client-isolation="pass"' not in dom:
    attrs = {}
    for name in (
        'data-new-client-isolation','data-summary-call-count','data-account-texts',
        'data-secret-texts','data-input-values','data-placeholders','data-unexpected-rpc-count',
    ):
        match = re.search(rf'{re.escape(name)}="([^"]*)"', dom)
        attrs[name] = match.group(1) if match else '__missing__'
    fail('new-client credential isolation regression failed: ' + json.dumps(attrs, ensure_ascii=False) + '; stderr=' + stderr[-1200:])

if 'data-summary-call-count="0"' not in dom:
    fail('create form still requested a previous client credential summary')
if 'previous-fb@example.test' in dom or 'previous-tk@example.test' in dom or '••••••••' in dom:
    fail('previous client credential state leaked into new-client DOM')
if 'data-unexpected-rpc-count="0"' not in dom:
    fail('new-client isolation invoked an unexpected RPC')

print(
    'BROWSER_NEW_CLIENT_CREDENTIAL_ISOLATION_OK: '
    f'browser={Path(browser).name}; client-form=create; stale-selected-client=ignored; '
    'safe-summary-rpc=not-called; previous-login+secret-status=absent; mutation-inputs=blank; placeholders=preserved'
)
