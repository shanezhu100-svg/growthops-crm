from pathlib import Path
import http.server
import json
import re
import shutil
import socket
import subprocess
import threading

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
HOTFIX = DIST / 'cloud-security-hotfix.js'


def fail(message: str) -> None:
    raise SystemExit('BROWSER_CLIENT_FORM_CREDENTIAL_STATUS_FAILED: ' + message)


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

# Synthetic-only fixture. It reproduces the client edit page while a stale account-
# assets aggregate selector remains 0. Persisted login/password state must render
# visually inside the matching input chrome without changing the input values. No
# real credential plaintext exists and the reveal RPC must never be called.
fixture = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"><title>credential form regression</title>
  <style>
    body{font:14px system-ui,sans-serif;padding:20px}
    .field{width:480px;margin:14px 0}
    .field label{display:block;margin-bottom:6px}
    .field input{display:block;width:100%;height:48px;box-sizing:border-box;padding:0 14px;font:14px system-ui,sans-serif}
  </style>
</head>
<body>
  <h1>Synthetic Client</h1>
  <section id="facebook-section">
    <h2>Facebook 资产</h2>
    <div class="account-card" data-account="fb1">
      <div class="field"><label>登录账号</label><input id="fb-login" value="" placeholder="邮箱 / 个人号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="fb-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
  </section>
  <section id="tiktok-section">
    <h2>TikTok 资产</h2>
    <div class="account-card" data-account="tk1">
      <div class="field"><label>登录账号</label><input id="tk-login" value="" placeholder="邮箱 / 个人号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="tk-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
  </section>
  <script>
    window.__growthOpsCredentialSummaryCalls=[];
    window.__growthOpsUnexpectedRpc=[];
    window.__growthOpsVm={
      currentPage:'client-form',
      selectedClientId:'client-1',
      selectedAssetsClientId:0,
      currentUser:{id:'admin-1',role:'ADMIN'},
      clients:[{id:'client-1',name:'Synthetic Client'}],
      selectedClient:{
        id:'client-1',
        name:'Synthetic Client',
        fbAccounts:[{id:'fb1'}],
        tkAccounts:[{id:'tk1'}]
      },
      notify:()=>{},
      persist:()=>{},
      updateStorageUsage:()=>{},
      logAudit:()=>{}
    };
    window.__growthOpsCloud={
      rpc:(name,args)=>{
        if(name==='crm_client_account_safe_summary'){
          window.__growthOpsCredentialSummaryCalls.push(args||{});
          return Promise.resolve({
            facebook:{loginAccount:'fb-login@example.test',hasPassword:true,has2FA:true},
            tiktok:{loginAccount:'tk-login@example.test',hasPassword:true,has2FA:false}
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
      const accountHosts=[...document.querySelectorAll('[data-growthops-credential-form-status="account"]')];
      const secretHosts=[...document.querySelectorAll('[data-growthops-credential-form-status="secret"]')];
      const allHosts=[...accountHosts,...secretHosts];
      const accountTexts=accountHosts.map(node=>String(node.textContent||'').trim());
      const secretTexts=secretHosts.map(node=>String(node.textContent||'').trim());
      const inputIds=['fb-login','fb-secret','tk-login','tk-secret'];
      const inputs=inputIds.map(id=>document.getElementById(id));
      const inputValues=inputs.map(node=>node?.value??'__missing__');
      const summaryCalls=window.__growthOpsCredentialSummaryCalls||[];
      const unexpected=window.__growthOpsUnexpectedRpc||[];
      const eyeButtons=secretHosts.map(node=>Boolean(node.querySelector('button[aria-label="显示密码和 2FA"]')));
      const overlayInsideInput=allHosts.map(host=>{
        const input=host.previousElementSibling;
        if(!input||!input.matches('input,textarea'))return false;
        const hr=host.getBoundingClientRect();
        const ir=input.getBoundingClientRect();
        return getComputedStyle(host).position==='absolute' &&
          hr.left>=ir.left-1 && hr.right<=ir.right+1 &&
          hr.top>=ir.top-1 && hr.bottom<=ir.bottom+1;
      });
      const savedPlaceholdersHidden=inputs.map(node=>String(node?.getAttribute('placeholder')||'')==='');
      const fbLogin=document.getElementById('fb-login');
      const fbAccountHost=accountHosts.find(host=>host.previousElementSibling===fbLogin);
      fbLogin?.focus();
      const focusHidesOverlay=Boolean(
        fbLogin && fbAccountHost &&
        getComputedStyle(fbAccountHost).visibility==='hidden' &&
        fbLogin.getAttribute('placeholder')==='邮箱 / 个人号'
      );
      const noSavedPrefix=accountTexts.every(text=>!text.includes('已保存：'));
      const pass=(
        accountHosts.length===2 &&
        secretHosts.length===2 &&
        accountTexts.includes('fb-login@example.test') &&
        accountTexts.includes('tk-login@example.test') &&
        noSavedPrefix &&
        secretTexts.every(text=>text.includes('••••••••')) &&
        eyeButtons.every(Boolean) &&
        overlayInsideInput.every(Boolean) &&
        savedPlaceholdersHidden.every(Boolean) &&
        focusHidesOverlay &&
        inputValues.every(value=>value==='') &&
        summaryCalls.length===1 &&
        String(summaryCalls[0]?.p_client_id||'')==='client-1' &&
        unexpected.length===0
      );
      document.body.setAttribute('data-credential-regression',pass?'pass':'fail');
      document.body.setAttribute('data-account-host-count',String(accountHosts.length));
      document.body.setAttribute('data-secret-host-count',String(secretHosts.length));
      document.body.setAttribute('data-input-values',JSON.stringify(inputValues));
      document.body.setAttribute('data-overlays-inside',JSON.stringify(overlayInsideInput));
      document.body.setAttribute('data-focus-hides-overlay',String(focusHidesOverlay));
      document.body.setAttribute('data-summary-client-id',String(summaryCalls[0]?.p_client_id||''));
      document.body.setAttribute('data-unexpected-rpc-count',String(unexpected.length));
    },1200);
  </script>
</body>
</html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

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
            body = HOTFIX.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
    '--virtual-time-budget=4000',
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
if 'data-credential-regression="pass"' not in dom:
    attrs = {}
    for name in (
        'data-credential-regression', 'data-account-host-count', 'data-secret-host-count',
        'data-input-values', 'data-overlays-inside', 'data-focus-hides-overlay',
        'data-summary-client-id', 'data-unexpected-rpc-count',
    ):
        match = re.search(rf'{re.escape(name)}="([^"]*)"', dom)
        attrs[name] = match.group(1) if match else '__missing__'
    fail('synthetic client-form regression failed: ' + json.dumps(attrs, ensure_ascii=False) + '; stderr=' + stderr[-1200:])

if 'fb-login@example.test' not in dom or 'tk-login@example.test' not in dom:
    fail('safe login summary text missing from rendered input overlay')
if '已保存：fb-login@example.test' in dom or '已保存：tk-login@example.test' in dom:
    fail('legacy below-input saved prefix remains')
if 'data-summary-client-id="client-1"' not in dom:
    fail('client-form did not use active selectedClientId')
if 'data-input-values="[&quot;&quot;,&quot;&quot;,&quot;&quot;,&quot;&quot;]"' not in dom and 'data-input-values="[\"\",\"\",\"\",\"\"]"' not in dom:
    fail('edit inputs were unexpectedly hydrated')
if 'data-focus-hides-overlay="true"' not in dom:
    fail('input focus did not hand control from saved overlay to mutation input')
if 'data-unexpected-rpc-count="0"' not in dom:
    fail('credential regression invoked an unexpected sensitive RPC')

print(
    'BROWSER_CLIENT_FORM_CREDENTIAL_STATUS_OK: '
    f'browser={Path(browser).name}; currentPage=client-form; stale-assets-id=0; '
    'safe-summary-client=client-1; facebook+tiktok=in-input-login+masked-eye; '
    'focus-edit=overlay-hidden; edit-input-values=blank; reveal-rpc=not-called'
)
