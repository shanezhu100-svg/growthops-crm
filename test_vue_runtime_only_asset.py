from pathlib import Path
import hashlib
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
URL = 'https://unpkg.com/vue@3.5.41/dist/vue.runtime.global.js'
EXPECTED_SHA256 = '__PROBE__'
EXPECTED_BYTES = 0


def fail(message: str) -> None:
    raise SystemExit('VUE_RUNTIME_ONLY_ASSET_FAILED: ' + message)


parsed = urllib.parse.urlsplit(URL)
if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
    fail('source URL must be an exact credential-free HTTPS resource')
request = urllib.request.Request(URL, headers={'User-Agent': 'growthops-crm-build/1'})
try:
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.geturl() != URL:
            fail('unexpected redirect: ' + response.geturl())
        data = response.read()
except SystemExit:
    raise
except Exception as exc:
    fail('download failed: ' + type(exc).__name__)

if len(data) < 300_000 or len(data) > 800_000:
    fail(f'unexpected runtime-only asset size: {len(data)} bytes')
try:
    text = data.decode('utf-8')
except UnicodeDecodeError:
    fail('runtime-only asset is not UTF-8 JavaScript')
for marker in ('vue v3.5.41', 'var Vue ='):
    if marker not in text:
        fail('runtime-only asset missing marker: ' + marker)
# Runtime-only global must not contain the full compiler entrypoint. Keep several
# independent markers so a packaging/layout drift cannot silently reintroduce it.
for forbidden in (
    'function compileToFunction(',
    'registerRuntimeCompiler(',
    'const compile = compileToFunction',
    'new Function(code)',
):
    if forbidden in text:
        fail('compiler-inclusive marker present: ' + forbidden)
# It should still expose the normal global runtime surface used by the app.
for marker in ('createApp', 'defineComponent', 'ref', 'computed', 'watch'):
    if marker not in text:
        fail('expected runtime API marker missing: ' + marker)

actual = hashlib.sha256(data).hexdigest()
if EXPECTED_SHA256 == '__PROBE__':
    fail(f'PIN_REQUIRED: sha256={actual}; bytes={len(data)}')
if actual != EXPECTED_SHA256 or len(data) != EXPECTED_BYTES:
    fail(f'asset drift: expected={EXPECTED_SHA256}/{EXPECTED_BYTES}B; actual={actual}/{len(data)}B')

# Prove the asset can initialize without a DOM and that no compiler is exposed.
probe = ROOT / '.tmp-vue-runtime-probe.js'
probe.write_bytes(data)
try:
    import subprocess
    js = r'''
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const sandbox = { console: { log(){}, info(){}, warn(){}, error(){} }, setTimeout, clearTimeout, setInterval, clearInterval };
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { timeout: 10000 });
if (!sandbox.Vue || typeof sandbox.Vue.createApp !== 'function') throw new Error('Vue runtime global missing createApp');
if (typeof sandbox.Vue.compile === 'function') throw new Error('runtime-only asset unexpectedly exposes compiler');
process.stdout.write('ok');
'''
    proc = subprocess.run(['node', '-e', js, str(probe)], capture_output=True, text=True, timeout=20, check=False)
    if proc.returncode != 0 or proc.stdout != 'ok':
        fail('runtime-only VM smoke failed: ' + re.sub(r'\s+', ' ', proc.stderr.strip())[:400])
finally:
    probe.unlink(missing_ok=True)

print(
    'VUE_RUNTIME_ONLY_ASSET_OK: version=3.5.41; global=runtime-only; compiler=absent; '
    f'sha256={actual}; bytes={len(data)}; redirect=denied; vm-smoke=pass'
)
