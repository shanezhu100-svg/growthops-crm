from pathlib import Path
import http.server
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
BROWSER_ATTEMPT_TIMEOUT_SECONDS = 20
MAX_BROWSER_ATTEMPTS = 2


def fail(message: str) -> None:
    raise SystemExit('BROWSER_MOUNT_SMOKE_FAILED: ' + message)


if not (DIST / 'index.html').is_file():
    fail('dist/index.html missing; run canonical build first')

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
base_cmd = [
    browser,
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-background-networking',
    '--disable-component-update',
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


def run_browser_attempt(attempt: int):
    # Give every attempt a fresh Chrome profile and process group. A transient
    # runner/Chrome shutdown hang must not leave descendants holding stdout/stderr
    # pipes indefinitely. Semantic mount assertions below are never retried or
    # weakened; only browser process launch/exit failures get one clean retry.
    with tempfile.TemporaryDirectory(prefix=f'growthops-browser-smoke-{attempt}-') as profile:
        cmd = [*base_cmd, f'--user-data-dir={profile}']
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=BROWSER_ATTEMPT_TIMEOUT_SECONDS)
            return proc.returncode, stdout or '', stderr or '', False
        except subprocess.TimeoutExpired as exc:
            partial_stdout = exc.stdout if isinstance(exc.stdout, str) else ''
            partial_stderr = exc.stderr if isinstance(exc.stderr, str) else ''
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                tail_stdout, tail_stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                tail_stdout, tail_stderr = '', ''
            return (
                None,
                partial_stdout + (tail_stdout or ''),
                partial_stderr + (tail_stderr or ''),
                True,
            )


proc_returncode = None
dom = ''
stderr = ''
process_failures = []
try:
    for attempt in range(1, MAX_BROWSER_ATTEMPTS + 1):
        returncode, stdout, raw_stderr, timed_out = run_browser_attempt(attempt)
        normalized_stderr = re.sub(r'\s+', ' ', raw_stderr or '').strip()
        if timed_out:
            process_failures.append(
                f'attempt={attempt}: timeout>{BROWSER_ATTEMPT_TIMEOUT_SECONDS}s; stderr={normalized_stderr[-800:]}'
            )
            continue
        if returncode != 0:
            process_failures.append(
                f'attempt={attempt}: exit={returncode}; stderr={normalized_stderr[-800:]}'
            )
            continue
        proc_returncode = returncode
        dom = stdout
        stderr = normalized_stderr
        break
finally:
    server.shutdown()
    server.server_close()

if proc_returncode != 0:
    fail('Chromium process did not complete cleanly after bounded retry: ' + ' | '.join(process_failures))

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
    f'browser={Path(browser).name}; v-cloak=removed; raw-template=consumed; dom-bytes={len(dom)}; '
    f'process-isolation=fresh-profile+process-group; attempts<={MAX_BROWSER_ATTEMPTS}; '
    f'attempt-timeout={BROWSER_ATTEMPT_TIMEOUT_SECONDS}s'
)
