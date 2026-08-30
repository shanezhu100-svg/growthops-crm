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


def fail(message: str) -> None:
    raise SystemExit('VUE_RUNTIME_STRICT_CSP_BROWSER_PROBE_FAILED: ' + message)


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

# Probe in an isolated copy. The canonical build output is never mutated by this
# experiment, so a failed runtime-only migration cannot leak into deployable dist/.
with tempfile.TemporaryDirectory(prefix='growthops-vue-runtime-probe-') as raw_tmp:
    work = Path(raw_tmp)
    shutil.copytree(DIST, work / 'dist')
    for name in ('vue_runtime_only_finalize.py', 'vue_runtime_compiled_marker_finalize.py'):
        shutil.copy2(ROOT / name, work / name)

    for script in ('vue_runtime_only_finalize.py', 'vue_runtime_compiled_marker_finalize.py'):
        proc = subprocess.run(
            ['python3', script],
            cwd=work,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            detail = re.sub(r'\s+', ' ', (proc.stdout + ' ' + proc.stderr).strip())[-1800:]
            fail(f'{script} failed: {detail}')

    probe_dist = work / 'dist'
    html = (probe_dist / 'index.html').read_text(encoding='utf-8')
    if '/vendor/vue-3.5.41.global.js' in html:
        fail('compiler-inclusive Vue script remains after runtime-only finalize')
    for required in (
        '/vendor/vue-3.5.41.runtime.global.js',
        '/vendor/vue-3.5.41.renders.js',
    ):
        if html.count(required) != 1:
            fail(f'runtime-only browser asset reference drift: {required}={html.count(required)}')

    registry = (probe_dist / 'vendor' / 'vue-3.5.41.renders.js').read_text(encoding='utf-8')
    if registry.count("Object.defineProperty(render, '_rc'") != 1:
        fail('runtime-compiled _rc compatibility marker missing')
    if 'new Function(' in registry or 'eval(' in registry:
        fail('render registry contains dynamic-code marker')

    strict_csp = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "frame-src 'none'; form-action 'self'; connect-src 'self'; script-src 'self'; "
        "script-src-attr 'none'; style-src 'self'; style-src-elem 'self'; "
        "style-src-attr 'none'; font-src 'self' data:; img-src 'self' data: blob:; "
        "media-src 'self' data: blob:; worker-src 'none'; manifest-src 'none'"
    )

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(probe_dist), **kwargs)

        def log_message(self, fmt, *args):
            pass

        def end_headers(self):
            self.send_header('Content-Security-Policy', strict_csp)
            self.send_header('X-Content-Type-Options', 'nosniff')
            super().end_headers()

        def do_POST(self):
            if self.path == '/api/crm':
                length = int(self.headers.get('Content-Length', '0') or '0')
                if length:
                    self.rfile.read(length)
                body = b'{"ok":false,"error":"STRICT_CSP_SMOKE_BACKEND_STUB"}'
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

    with tempfile.TemporaryDirectory(prefix='growthops-vue-runtime-chrome-') as profile:
        cmd = [
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
            '--virtual-time-budget=7000',
            '--dump-dom',
            f'--user-data-dir={profile}',
            url,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            dom, stderr = proc.communicate(timeout=25)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                tail_out, tail_err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                tail_out, tail_err = '', ''
            partial = (exc.stderr if isinstance(exc.stderr, str) else '') + (tail_err or '')
            server.shutdown()
            server.server_close()
            fail('Chromium timeout; stderr=' + re.sub(r'\s+', ' ', partial)[-1600:])
        finally:
            server.shutdown()
            server.server_close()

    normalized_stderr = re.sub(r'\s+', ' ', stderr or '').strip()
    if proc.returncode != 0:
        fail(f'Chromium exit={proc.returncode}; stderr={normalized_stderr[-1800:]}')
    if len(dom) < 1000:
        fail(f'dumped DOM unexpectedly small: {len(dom)} bytes; stderr={normalized_stderr[-1800:]}')

    app_match = re.search(r'<div\s+[^>]*id=["\']app["\'][^>]*>', dom, re.I)
    if not app_match:
        fail('mounted DOM has no #app root')
    if 'v-cloak' in app_match.group(0).lower():
        fail('Vue did not mount under strict CSP; chromium-stderr=' + normalized_stderr[-2200:])
    if '{{ currentuser' in dom.lower() or 'v-if="!loggedin"' in dom.lower():
        fail('raw Vue template markers remain under strict CSP')

    text = re.sub(r'<[^>]+>', ' ', dom)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 40:
        fail('mounted strict-CSP page has no meaningful visible text')

    csp_errors = [
        part for part in normalized_stderr.split(']')
        if 'content security policy' in part.lower() or 'unsafe-eval' in part.lower()
    ]
    if csp_errors:
        fail('Chromium reported CSP execution violation: ' + ' | '.join(csp_errors[-3:])[-1800:])

print(
    'VUE_RUNTIME_STRICT_CSP_BROWSER_PROBE_OK: '
    'isolated-dist=true; runtime-only=true; compiled-marker=_rc; '
    "script-src='self'; unsafe-eval=absent; real-chromium-mount=pass"
)
