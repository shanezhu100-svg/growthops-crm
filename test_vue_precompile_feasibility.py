from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'


def fail(message: str) -> None:
    raise SystemExit('VUE_PRECOMPILE_FEASIBILITY_FAILED: ' + message)


def extract_app_inner_html(source: str) -> str:
    opening = re.search(
        r'<([A-Za-z][\w:-]*)\b(?=[^>]*\bid\s*=\s*["\']app["\'])[^>]*>',
        source,
        flags=re.I | re.S,
    )
    if not opening:
        fail('root #app opening element not found')
    tag = opening.group(1)
    token_re = re.compile(r'<!--.*?-->|</?' + re.escape(tag) + r'\b[^>]*>', re.I | re.S)
    depth = 1
    for match in token_re.finditer(source, opening.end()):
        token = match.group(0)
        if token.startswith('<!--'):
            continue
        if re.match(r'</', token):
            depth -= 1
            if depth == 0:
                return source[opening.end():match.start()]
        elif not re.search(r'/\s*>$', token):
            depth += 1
    fail('root #app closing element not found')


def extract_template_literals(source: str) -> list[str]:
    templates = []
    marker = re.compile(r'(?<![\w$])template\s*:\s*`')
    for match in marker.finditer(source):
        i = match.end()
        start = i
        escaped = False
        while i < len(source):
            ch = source[i]
            if ch == '`' and not escaped:
                templates.append(source[start:i])
                break
            if ch == '\\':
                escaped = not escaped
            else:
                escaped = False
            i += 1
        else:
            fail('unterminated component template literal')
    return templates


for path in [INDEX, VUE_ASSET, *APP_FILES]:
    if not path.is_file():
        fail(f'missing build artifact: {path.relative_to(ROOT)}')

html = INDEX.read_text(encoding='utf-8')
app_js = '\n'.join(path.read_text(encoding='utf-8') for path in APP_FILES)
root_template = extract_app_inner_html(html)
component_templates = extract_template_literals(app_js)
if len(component_templates) != 4:
    fail(f'expected 4 component template literals, found {len(component_templates)}')
if len(root_template.encode('utf-8')) < 100_000:
    fail('root template unexpectedly small')

units = [{'name': 'root', 'template': root_template}]
units.extend(
    {'name': f'component-{idx:02d}', 'template': template}
    for idx, template in enumerate(component_templates, start=1)
)

node_probe = r'''
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const vueSource = fs.readFileSync(input.vuePath, 'utf8');
const sha = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');

function compilePass() {
  const sandbox = {
    console: { log(){}, info(){}, warn(){}, error(){} },
    setTimeout, clearTimeout, setInterval, clearInterval,
  };
  vm.createContext(sandbox);
  vm.runInContext(vueSource, sandbox, { filename: 'vue-3.5.41.global.js', timeout: 10000 });
  if (!sandbox.Vue || typeof sandbox.Vue.compile !== 'function') {
    throw new Error('Vue.compile unavailable');
  }
  const NativeFunction = vm.runInContext('Function', sandbox);
  let captures = [];
  const WrappedFunction = function(...args) {
    captures.push(args.map((arg) => String(arg)));
    return NativeFunction(...args);
  };
  WrappedFunction.prototype = NativeFunction.prototype;
  sandbox.Function = WrappedFunction;

  const out = [];
  for (const unit of input.units) {
    captures = [];
    const render = sandbox.Vue.compile(unit.template);
    if (typeof render !== 'function') throw new Error(unit.name + ': compile did not return function');
    const renderSource = Function.prototype.toString.call(render);
    const normalizedCaptures = captures.map((args) => ({
      argc: args.length,
      argBytes: args.map((arg) => Buffer.byteLength(arg, 'utf8')),
      argHashes: args.map(sha),
    }));
    out.push({
      name: unit.name,
      templateBytes: Buffer.byteLength(unit.template, 'utf8'),
      templateHash: sha(unit.template),
      renderBytes: Buffer.byteLength(renderSource, 'utf8'),
      renderHash: sha(renderSource),
      captures: normalizedCaptures,
    });
  }
  return out;
}

const first = compilePass();
const second = compilePass();
process.stdout.write(JSON.stringify({ first, second }));
'''

payload = json.dumps({'vuePath': str(VUE_ASSET), 'units': units}, ensure_ascii=False)
try:
    proc = subprocess.run(
        ['node', '-e', node_probe],
        input=payload,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
except Exception as exc:
    fail('node probe launch failed: ' + type(exc).__name__)
if proc.returncode != 0:
    detail = re.sub(r'\s+', ' ', proc.stderr.strip())[:500]
    fail(f'node probe failed rc={proc.returncode}: {detail}')
try:
    result = json.loads(proc.stdout)
except Exception:
    fail('node probe returned invalid JSON')
first = result.get('first')
second = result.get('second')
if not isinstance(first, list) or not isinstance(second, list) or len(first) != 5 or len(second) != 5:
    fail('unexpected compile result inventory')
if first != second:
    fail('compiler output is not deterministic across isolated VM passes')

summary = []
for item in first:
    captures = item.get('captures') or []
    if len(captures) != 1:
        fail(f"{item.get('name')}: expected one Function compilation capture, found {len(captures)}")
    capture = captures[0]
    if capture.get('argc') not in (1, 2):
        fail(f"{item.get('name')}: unexpected Function argument count {capture.get('argc')}")
    if not capture.get('argBytes') or max(capture['argBytes']) < 100:
        fail(f"{item.get('name')}: captured compiler code unexpectedly small")
    summary.append(
        f"{item['name']}="
        f"tpl:{item['templateHash'][:12]}/{item['templateBytes']}B,"
        f"render:{item['renderHash'][:12]}/{item['renderBytes']}B,"
        f"capture:{capture['argc']}args/"
        + '+'.join(str(n) for n in capture['argBytes'])
        + 'B/'
        + '+'.join(h[:12] for h in capture['argHashes'])
    )

# First run is intentionally a fail-closed evidence probe. After the exact hashes
# below are reviewed, replace this terminal probe with pinned deterministic asserts.
raise SystemExit(
    'VUE_PRECOMPILE_FEASIBILITY_PROBE: units=5; deterministic=2-vm-pass; '
    + '; '.join(summary)
)
