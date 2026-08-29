from pathlib import Path
import http.server
import os
import re
import shutil
import socket
import subprocess
import threading

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'


def fail(message: str) -> None:
    raise SystemExit('BROWSER_MOUNT_SMOKE_FAILED: ' + message)


if not (DIST / 'index.html').is_file():
    fail('dist/index.html missing; run canonical build first')

# The real browser smoke is a merge gate, not a deployment-host dependency.
# GitHub Actions is the required protected-main `build` context and provides the
# Chromium executable used for this test. Vercel/Cloudflare deployment images are
# allowed to omit Chromium; they deploy only commits whose required GitHub build
# has already passed the real-browser mount invariant.
if os.environ.get('GITHUB_ACTIONS') != 'true':
    print(
        'BROWSER_MOUNT_SMOKE_SKIPPED: '
        'real-browser-required-in=github-actions; deploy-build=uses-protected-main-gate'
    )
    raise SystemExit(0)

browser = next(
    (
        shutil.which(name)
        for name in ('google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser')
        if shutil.which(name)
    ),
    None,
)
if not browser:
    fail('no supported Chromium executable on required GitHub Actions runner')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        # The smoke test is about real browser parsing/execution/mounting, not
        # backend semantics. Keep same-origin startup fetches deterministic and
        # harmless so a missing API cannot mask a frontend mount regression.
        if self.path == '/api/crm':
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length:
                self.rfile.read(length)
            body = b'{"ok":false,"error":"SMOKE_BACKEND_STUB"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
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

url = f'http://127.0.0.1:{port}/'
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
    '--virtual-time-budget=6000',
    '--dump-dom',
    url,
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
if len(dom) < 1000:
    fail(f'dumped DOM unexpectedly small: {len(dom)} bytes; stderr={stderr[-1600:]}')

app_match = re.search(r'<div\s+[^>]*id=["\']app["\'][^>]*>', dom, re.I)
if not app_match:
    fail('mounted DOM has no #app root')
app_tag = app_match.group(0).lower()
if 'v-cloak' in app_tag:
    fail('Vue never mounted: #app still has v-cloak; chromium-stderr=' + stderr[-2000:])

# A mounted render must consume Vue interpolation/directive source rather than
# leave the original hidden template untouched.
if '{{ currentuser' in dom.lower() or 'v-if="!loggedin"' in dom.lower():
    fail('raw Vue template markers remain after browser execution')

# Keep a broad visible-shell assertion instead of pinning product copy exactly.
text = re.sub(r'<[^>]+>', ' ', dom)
text = re.sub(r'\s+', ' ', text).strip()
if len(text) < 40:
    fail('mounted page has no meaningful visible text; chromium-stderr=' + stderr[-2000:])

print(
    'BROWSER_MOUNT_SMOKE_OK: '
    f'browser={Path(browser).name}; v-cloak=removed; raw-template=consumed; dom-bytes={len(dom)}'
)
