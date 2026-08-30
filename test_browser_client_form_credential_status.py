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

# Synthetic-only fixture. It reproduces the exact multi-account client-edit boundary
# from the reported screen: two Facebook cards plus two TikTok cards. Internal account
# IDs deliberately do NOT appear in card text, so a refresh/reopen cannot rely on a
# visible ID token to reconnect the Vault safe summary to each blank mutation input.
# The edit-only ordinal fallback must keep each saved login/password status on the
# correct card. No real credential plaintext exists and no reveal RPC may run during
# passive render/click/focus.
fixture = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"><title>credential form multi-account regression</title>
  <link rel="stylesheet" href="/vendor/fontawesome/css/all.min.css">
  <style>
    body{font:14px system-ui,sans-serif;padding:20px}
    .field{width:480px;margin:14px 0}
    .field label{display:block;margin-bottom:6px}
    .field input{display:block;width:100%;height:48px;box-sizing:border-box;padding:0 14px;font:14px system-ui,sans-serif}
    .account-card{padding:12px;margin:12px 0;border:1px solid #ddd}
  </style>
</head>
<body>
  <h1>Synthetic Client</h1>
  <section id="facebook-section">
    <h2>Facebook 资产</h2>
    <div class="account-card">
      <h3>电动叉车</h3>
      <div class="field"><label>登录账号</label><input id="fb1-login" value="" placeholder="邮箱 / 个人号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="fb1-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
    <div class="account-card">
      <h3>工程机械</h3>
      <div class="field"><label>登录账号</label><input id="fb2-login" value="" placeholder="邮箱 / 个人号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="fb2-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
  </section>
  <section id="tiktok-section">
    <h2>TikTok 资产</h2>
    <div class="account-card">
      <h3>电动叉车</h3>
      <div class="field"><label>登录账号</label><input id="tk1-login" value="" placeholder="邮箱 / TikTok 账号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="tk1-secret" value="" placeholder="密码 / 2FA Token"></div>
    </div>
    <div class="account-card">
      <h3>工程机械</h3>
      <div class="field"><label>登录账号</label><input id="tk2-login" value="" placeholder="邮箱 / TikTok 账号"></div>
      <div class="field"><label>密码 / 2FA</label><input id="tk2-secret" value="" placeholder="密码 / 2FA Token"></div>
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
        fbAccounts:[{id:'fb-internal-1'},{id:'fb-internal-2'}],
        tkAccounts:[{id:'tk-internal-1'},{id:'tk-internal-2'}]
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
            facebookAccounts:[
              {id:'fb-internal-1',loginAccount:'fb-one@example.test',hasPassword:true,has2FA:true},
              {id:'fb-internal-2',loginAccount:'fb-two@example.test',hasPassword:true,has2FA:false}
            ],
            tiktokAccounts:[
              {id:'tk-internal-1',loginAccount:'tk-one@example.test',hasPassword:true,has2FA:false},
              {id:'tk-internal-2',loginAccount:'tk-two@example.test',hasPassword:true,has2FA:true}
            ],
            // Deliberately wrong legacy values: multi-account edit must never reuse them.
            facebook:{loginAccount:'legacy-fb-wrong@example.test',hasPassword:false,has2FA:false},
            tiktok:{loginAccount:'legacy-tk-wrong@example.test',hasPassword:false,has2FA:false}
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
      const inputIds=['fb1-login','fb1-secret','fb2-login','fb2-secret','tk1-login','tk1-secret','tk2-login','tk2-secret'];
      const inputs=inputIds.map(id=>document.getElementById(id));
      const initialInputValues=inputs.map(node=>node?.value??'__missing__');
      const summaryCalls=window.__growthOpsCredentialSummaryCalls||[];
      const unexpected=window.__growthOpsUnexpectedRpc||[];
      const expectedAccounts=['fb-one@example.test','fb-two@example.test','tk-one@example.test','tk-two@example.test'];

      const eyeIntegrity=secretHosts.map(host=>{
        const input=host.previousElementSibling;
        const button=host.querySelector('button[aria-label="显示密码和 2FA"]');
        const icon=button?.querySelector('i.fa-eye');
        if(!input||!button||!icon)return false;
        const br=button.getBoundingClientRect();
        const ir=input.getBoundingClientRect();
        const xr=icon.getBoundingClientRect();
        const bs=getComputedStyle(button);
        const hs=getComputedStyle(host);
        if(bs.display==='none'||bs.visibility==='hidden'||Number(bs.opacity||1)<=0)return false;
        if(hs.visibility==='hidden')return false;
        if(br.width<24||br.height<24||xr.width<4||xr.height<4)return false;
        if(br.left<ir.left-1||br.right>ir.right+1||br.top<ir.top-1||br.bottom>ir.bottom+1)return false;
        const x=br.left+br.width/2;
        const y=br.top+br.height/2;
        const hit=document.elementFromPoint(x,y);
        return hit===button||button.contains(hit);
      });

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

      const fbLogin=document.getElementById('fb1-login');
      const fbAccountHost=accountHosts.find(host=>host.previousElementSibling===fbLogin);
      fbAccountHost?.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));
      const clickPreservesSavedAccount=Boolean(
        fbLogin && fbAccountHost && document.activeElement===fbLogin &&
        getComputedStyle(fbAccountHost).visibility==='visible' &&
        String(fbAccountHost.textContent||'').trim()==='fb-one@example.test' &&
        fbLogin.getAttribute('placeholder')===''
      );

      if(fbLogin){
        fbLogin.value='replacement-login@example.test';
        fbLogin.dispatchEvent(new Event('input',{bubbles:true}));
      }
      const typingHandsOffToMutation=Boolean(
        fbLogin && fbAccountHost &&
        getComputedStyle(fbAccountHost).visibility==='hidden' &&
        fbLogin.value==='replacement-login@example.test' &&
        fbLogin.getAttribute('placeholder')==='邮箱 / 个人号'
      );

      const noSavedPrefix=accountTexts.every(text=>!text.includes('已保存：'));
      const exactAccountCorrespondence=expectedAccounts.every((value,index)=>accountTexts[index]===value);
      const noLegacyReuse=accountTexts.every(text=>!text.includes('legacy-'));
      const pass=(
        accountHosts.length===4 &&
        secretHosts.length===4 &&
        exactAccountCorrespondence &&
        noLegacyReuse &&
        noSavedPrefix &&
        secretTexts.every(text=>text.includes('••••••••')) &&
        eyeIntegrity.every(Boolean) &&
        overlayInsideInput.every(Boolean) &&
        savedPlaceholdersHidden.every(Boolean) &&
        clickPreservesSavedAccount &&
        typingHandsOffToMutation &&
        initialInputValues.every(value=>value==='') &&
        summaryCalls.length===1 &&
        String(summaryCalls[0]?.p_client_id||'')==='client-1' &&
        unexpected.length===0
      );
      document.body.setAttribute('data-credential-regression',pass?'pass':'fail');
      document.body.setAttribute('data-account-host-count',String(accountHosts.length));
      document.body.setAttribute('data-secret-host-count',String(secretHosts.length));
      document.body.setAttribute('data-account-texts',JSON.stringify(accountTexts));
      document.body.setAttribute('data-exact-account-correspondence',String(exactAccountCorrespondence));
      document.body.setAttribute('data-no-legacy-reuse',String(noLegacyReuse));
      document.body.setAttribute('data-initial-input-values',JSON.stringify(initialInputValues));
      document.body.setAttribute('data-overlays-inside',JSON.stringify(overlayInsideInput));
      document.body.setAttribute('data-eye-integrity',JSON.stringify(eyeIntegrity));
      document.body.setAttribute('data-click-preserves-saved-account',String(clickPreservesSavedAccount));
      document.body.setAttribute('data-typing-handoff',String(typingHandsOffToMutation));
      document.body.setAttribute('data-summary-client-id',String(summaryCalls[0]?.p_client_id||''));
      document.body.setAttribute('data-unexpected-rpc-count',String(unexpected.length));
    },1400);
  </script>
</body>
</html>'''


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
        elif path.suffix == '.css':
            content_type = 'text/css; charset=utf-8'
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
        if self.path.startswith('/vendor/fontawesome/'):
            relative = self.path.lstrip('/')
            target = (DIST / relative).resolve()
            vendor_root = (DIST / 'vendor' / 'fontawesome').resolve()
            if target != vendor_root and vendor_root not in target.parents:
                self.send_error(403)
                return
            self.send_file(target)
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
    '--virtual-time-budget=5000',
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
        'data-account-texts', 'data-exact-account-correspondence', 'data-no-legacy-reuse',
        'data-initial-input-values', 'data-overlays-inside', 'data-eye-integrity',
        'data-click-preserves-saved-account', 'data-typing-handoff',
        'data-summary-client-id', 'data-unexpected-rpc-count',
    ):
        match = re.search(rf'{re.escape(name)}="([^"]*)"', dom)
        attrs[name] = match.group(1) if match else '__missing__'
    fail('synthetic client-form multi-account regression failed: ' + json.dumps(attrs, ensure_ascii=False) + '; stderr=' + stderr[-1200:])

for value in ('fb-one@example.test','fb-two@example.test','tk-one@example.test','tk-two@example.test'):
    if value not in dom:
        fail('safe login summary missing from rendered input overlay: ' + value)
if 'legacy-fb-wrong@example.test' in dom or 'legacy-tk-wrong@example.test' in dom:
    fail('multi-account edit reused legacy platform-level summary')
if 'data-exact-account-correspondence="true"' not in dom:
    fail('multi-account saved credential summaries did not follow card order')
if 'data-no-legacy-reuse="true"' not in dom:
    fail('legacy platform summary leaked into multi-account edit')
if 'data-summary-client-id="client-1"' not in dom:
    fail('client-form did not use active selectedClientId')
if 'data-click-preserves-saved-account="true"' not in dom:
    fail('clicking saved login account still makes the visible identifier disappear')
if 'data-typing-handoff="true"' not in dom:
    fail('actual typed replacement did not hand off to mutation input')
if 'data-eye-integrity="[true,true,true,true]"' not in dom and 'data-eye-integrity="[true, true, true, true]"' not in dom:
    fail('password eye controls are not all visibly rendered and hit-testable')
if 'data-unexpected-rpc-count="0"' not in dom:
    fail('credential regression invoked an unexpected sensitive RPC')

print(
    'BROWSER_CLIENT_FORM_CREDENTIAL_STATUS_OK: '
    f'browser={Path(browser).name}; currentPage=client-form; stale-assets-id=0; '
    'facebook=2+tiktok=2; safe-summary=per-account+edit-order-fallback; '
    'click=preserves-saved-account; typing=mutation-handoff; eye=4-visible+hit-testable; '
    'initial-edit-values=blank; legacy-platform-summary=not-reused; reveal-rpc=not-called'
)
