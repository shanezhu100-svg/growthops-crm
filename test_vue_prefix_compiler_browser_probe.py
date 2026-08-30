from html.parser import HTMLParser
from pathlib import Path
import hashlib
import http.server
import json
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
    raise SystemExit('VUE_PREFIX_COMPILER_BROWSER_PROBE_FAILED: ' + message)


def extract_root(source: str) -> str:
    starts = [0]
    for match in re.finditer(r'\n', source):
        starts.append(match.end())

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.tag = None
            self.inner_start = None
            self.ends = []
            self.body_end = None
            self.roots = 0

        def pos(self):
            line, offset = self.getpos()
            return starts[line - 1] + offset

        def handle_starttag(self, tag, attrs):
            if dict(attrs).get('id') != 'app':
                return
            self.roots += 1
            self.tag = tag.lower()
            self.inner_start = self.pos() + len(self.get_starttag_text())

        def handle_endtag(self, tag):
            pos = self.pos()
            low = tag.lower()
            if low == 'body':
                self.body_end = pos
            if self.tag and low == self.tag and self.inner_start is not None and pos > self.inner_start:
                self.ends.append(pos)

    parser = Parser()
    parser.feed(source)
    parser.close()
    if parser.roots != 1 or parser.inner_start is None or parser.body_end is None:
        fail('root #app boundary drift')
    ends = [pos for pos in parser.ends if pos < parser.body_end]
    if not ends:
        fail('root #app closing boundary drift')
    return source[parser.inner_start:max(ends)]


def component_templates(source: str) -> list[str]:
    out = []
    marker = re.compile(r'(?<![\w$])template\s*:\s*`')
    for match in marker.finditer(source):
        i = match.end()
        start = i
        escaped = False
        while i < len(source):
            ch = source[i]
            if ch == '`' and not escaped:
                out.append(source[start:i])
                break
            escaped = (ch == '\\' and not escaped)
            if ch != '\\':
                escaped = False
            i += 1
        else:
            fail('unterminated component template')
    return out


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
if not shutil.which('npm') or not shutil.which('node'):
    fail('Node/npm toolchain missing')

html = (DIST / 'index.html').read_text(encoding='utf-8')
app_files = [DIST / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]
if any(not path.is_file() for path in app_files):
    fail('final app-inline inventory missing')
blocks = [path.read_text(encoding='utf-8') for path in app_files]
entries = component_templates(blocks[2])
if [len(component_templates(block)) for block in blocks] != [0, 0, 4]:
    fail('component template layout drifted before prefix probe')
units = [{'name': 'root', 'template': extract_root(html)}]
units.extend({'name': f'component{idx:02d}', 'template': template} for idx, template in enumerate(entries, 1))

with tempfile.TemporaryDirectory(prefix='growthops-vue-prefix-probe-') as raw_tmp:
    work = Path(raw_tmp)
    compiler_dir = work / 'compiler'
    compiler_dir.mkdir()
    install = subprocess.run(
        [
            'npm', 'install', '--prefix', str(compiler_dir), '--ignore-scripts',
            '--no-audit', '--no-fund', '--package-lock=false', '@vue/compiler-dom@3.5.41',
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if install.returncode != 0:
        detail = re.sub(r'\s+', ' ', (install.stdout + ' ' + install.stderr).strip())[-1400:]
        fail('temporary @vue/compiler-dom install failed: ' + detail)

    shutil.copytree(DIST, work / 'dist')
    shutil.copy2(ROOT / 'vue_runtime_only_finalize.py', work / 'vue_runtime_only_finalize.py')
    rewrite = subprocess.run(
        ['python3', 'vue_runtime_only_finalize.py'],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if rewrite.returncode != 0:
        detail = re.sub(r'\s+', ' ', (rewrite.stdout + ' ' + rewrite.stderr).strip())[-1600:]
        fail('runtime-only transport rewrite failed: ' + detail)

    registry_path = work / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'
    node_probe = r'''
const fs = require('fs');
const crypto = require('crypto');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const { compile } = require(input.compilerModule);
const sha = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');
const records = [];
const lines = [
  '/* GrowthOps CRM: Node compiler-dom prefixIdentifiers feasibility registry. */',
  '(function () {',
  '  const renders = Object.freeze({'
];
for (let index = 0; index < input.units.length; index += 1) {
  const unit = input.units[index];
  const result = compile(unit.template, {
    mode: 'function',
    prefixIdentifiers: true,
    hoistStatic: true,
    cacheHandlers: false,
  });
  const code = String(result.code || '');
  if (!code.includes('return function render')) throw new Error(unit.name + ': render factory missing');
  if (/\bwith\s*\(\s*_ctx\s*\)/.test(code)) throw new Error(unit.name + ': with(_ctx) remains');
  if (/\bnew\s+Function\s*\(/.test(code) || /\beval\s*\(/.test(code)) throw new Error(unit.name + ': dynamic-code marker in generated factory');
  if (unit.name === 'root' && !code.includes('_ctx.pageEyebrow')) throw new Error('root: pageEyebrow is not explicitly prefixed');
  const comma = index + 1 < input.units.length ? ',' : '';
  lines.push(`    ${unit.name}: (function () {`);
  for (const line of code.split('\n')) lines.push('      ' + line);
  lines.push(`    })()${comma}`);
  records.push({ name: unit.name, sha256: sha(code), bytes: Buffer.byteLength(code, 'utf8') });
}
lines.push('  });');
lines.push("  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {");
lines.push('    value: renders, writable: false, configurable: false, enumerable: false');
lines.push('  });');
lines.push('})();');
lines.push('');
const registry = lines.join('\n');
if (/\bwith\s*\(\s*_ctx\s*\)/.test(registry)) throw new Error('registry with(_ctx) remains');
if (/\bnew\s+Function\s*\(/.test(registry) || /\beval\s*\(/.test(registry)) throw new Error('registry dynamic-code marker');
fs.writeFileSync(input.registryPath, registry, 'utf8');
process.stdout.write(JSON.stringify({ records, registrySha: sha(registry), registryBytes: Buffer.byteLength(registry, 'utf8') }));
'''
    compiler_module = compiler_dir / 'node_modules' / '@vue' / 'compiler-dom'
    payload = json.dumps(
        {
            'compilerModule': str(compiler_module),
            'registryPath': str(registry_path),
            'units': units,
        },
        ensure_ascii=False,
    )
    compiled = subprocess.run(
        ['node', '-e', node_probe],
        input=payload,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if compiled.returncode != 0:
        detail = re.sub(r'\s+', ' ', compiled.stderr.strip())[-1600:]
        fail('prefixIdentifiers compiler probe failed: ' + detail)
    try:
        evidence = json.loads(compiled.stdout)
    except Exception:
        fail('prefixIdentifiers compiler probe returned invalid JSON')
    if len(evidence.get('records', [])) != 5:
        fail('prefix compiler unit inventory drift')

    registry = registry_path.read_text(encoding='utf-8')
    if 'with (_ctx)' in registry or 'with(_ctx)' in registry:
        fail('with(_ctx) remains in written prefix registry')
    if '_ctx.pageEyebrow' not in registry:
        fail('pageEyebrow is not context-prefixed in written registry')

    probe_dist = work / 'dist'
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
                body = b'{"ok":false,"error":"PREFIX_COMPILER_SMOKE_BACKEND_STUB"}'
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

    with tempfile.TemporaryDirectory(prefix='growthops-vue-prefix-chrome-') as profile:
        cmd = [
            browser, '--headless=new', '--no-sandbox', '--disable-gpu',
            '--disable-dev-shm-usage', '--disable-background-networking',
            '--disable-component-update', '--disable-default-apps', '--disable-extensions',
            '--disable-sync', '--metrics-recording-only', '--no-first-run',
            '--enable-logging=stderr', '--v=0', '--virtual-time-budget=7000', '--dump-dom',
            f'--user-data-dir={profile}', f'http://127.0.0.1:{port}/',
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
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
            fail('Chromium timeout; stderr=' + re.sub(r'\s+', ' ', partial)[-1600:])
        finally:
            server.shutdown()
            server.server_close()

    stderr = re.sub(r'\s+', ' ', stderr or '').strip()
    if proc.returncode != 0:
        fail(f'Chromium exit={proc.returncode}; stderr={stderr[-1800:]}')
    app_match = re.search(r'<div\s+[^>]*id=["\']app["\'][^>]*>', dom, re.I)
    if not app_match:
        fail('mounted DOM has no #app root')
    if 'v-cloak' in app_match.group(0).lower():
        fail('prefixed runtime-only Vue did not mount; chromium-stderr=' + stderr[-2200:])
    if '{{ currentuser' in dom.lower() or 'v-if="!loggedin"' in dom.lower():
        fail('raw Vue template markers remain after prefixed runtime-only mount')
    if 'uncaught referenceerror' in stderr.lower() or 'content security policy' in stderr.lower():
        fail('browser execution error under strict CSP: ' + stderr[-2200:])
    visible = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', dom)).strip()
    if len(visible) < 40:
        fail('mounted prefixed runtime-only page has no meaningful visible text')

    registry_sha = hashlib.sha256(registry.encode('utf-8')).hexdigest()
    print(
        'VUE_PREFIX_COMPILER_BROWSER_PROBE_OK: '
        f'compiler-dom=3.5.41; units=5; registry={registry_sha}/{len(registry.encode("utf-8"))}B; '
        "prefixIdentifiers=true; with(_ctx)=absent; pageEyebrow=_ctx-prefixed; script-src='self'; "
        'unsafe-eval=absent; real-chromium-mount=pass'
    )
