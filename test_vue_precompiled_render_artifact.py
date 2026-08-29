from html.entities import html5 as HTML5_ENTITIES
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'
EXPECTED_FACTORY_HASHES = {
    'root': '51cca92d97aaacfe925d7e8d54fc33fcf265ffdec549062d091282f9220b050d',
    'component01': '12ce20f7003c90017ebf8cd31e97bc632eb90518176775dbfe663c9b9166fae6',
    'component02': '7a99ecc1e3f6f9d2d14501681e630c40fa59f94144a50d72f392aa757732dcd7',
    'component03': '658b8af682a2023c6e01515def82b39f1fcaf5fe7a7315c582e298ff0c3a85be',
    'component04': '0ca46a8239700de84f36e527fc8bef3d737fdb09fb78fa64c5242a9ba4d8bb87',
}
EXPECTED_ASSET_SHA256 = '__PROBE__'
EXPECTED_ASSET_BYTES = 0


def fail(message: str) -> None:
    raise SystemExit('VUE_PRECOMPILED_RENDER_ARTIFACT_FAILED: ' + message)


def extract_root(source: str) -> str:
    line_starts = [0]
    for match in re.finditer(r'\n', source):
        line_starts.append(match.end())

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.root_tag = None
            self.inner_start = None
            self.root_ends = []
            self.body_end = None
            self.roots = 0

        def pos(self):
            line, offset = self.getpos()
            return line_starts[line - 1] + offset

        def handle_starttag(self, tag, attrs):
            if dict(attrs).get('id') != 'app':
                return
            self.roots += 1
            if self.roots != 1:
                fail('multiple #app roots')
            self.root_tag = tag.lower()
            self.inner_start = self.pos() + len(self.get_starttag_text())

        def handle_endtag(self, tag):
            low = tag.lower()
            p = self.pos()
            if low == 'body':
                self.body_end = p
            if self.root_tag and low == self.root_tag and self.inner_start is not None and p > self.inner_start:
                self.root_ends.append(p)

    parser = Parser()
    parser.feed(source)
    parser.close()
    if parser.roots != 1 or parser.inner_start is None or parser.body_end is None:
        fail('root/body boundary missing')
    ends = [p for p in parser.root_ends if p < parser.body_end]
    if not ends:
        fail('root closing boundary missing')
    template = source[parser.inner_start:max(ends)]
    if len(template.encode('utf-8')) < 100_000:
        fail('root template unexpectedly small')
    return template


def extract_component_templates(source: str) -> list[str]:
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


for path in [INDEX, VUE_ASSET, *APP_FILES]:
    if not path.is_file():
        fail('missing build artifact: ' + str(path.relative_to(ROOT)))

html = INDEX.read_text(encoding='utf-8')
app_js = '\n'.join(path.read_text(encoding='utf-8') for path in APP_FILES)
component_templates = extract_component_templates(app_js)
if len(component_templates) != 4:
    fail(f'expected 4 component templates, found {len(component_templates)}')
units = [{'name': 'root', 'template': extract_root(html)}]
units.extend({'name': f'component{idx:02d}', 'template': tpl} for idx, tpl in enumerate(component_templates, 1))

node_compile = r'''
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const vueSource = fs.readFileSync(input.vuePath, 'utf8');
const sha = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');
function decodeEntities(raw) {
  let out = '';
  for (let i = 0; i < raw.length;) {
    if (raw[i] !== '&') { out += raw[i++]; continue; }
    const start = i++;
    if (raw[i] === '#') {
      let j = i + 1, radix = 10;
      if (raw[j] === 'x' || raw[j] === 'X') { radix = 16; j += 1; }
      const ds = j;
      while (j < raw.length && (radix === 16 ? /[0-9A-Fa-f]/.test(raw[j]) : /[0-9]/.test(raw[j]))) j += 1;
      if (j === ds) { out += '&'; continue; }
      const value = Number.parseInt(raw.slice(ds, j), radix);
      if (raw[j] === ';') j += 1;
      const valid = value > 0 && value <= 0x10ffff && !(value >= 0xd800 && value <= 0xdfff);
      out += String.fromCodePoint(valid ? value : 0xfffd); i = j; continue;
    }
    let j = i;
    while (j < raw.length && /[0-9A-Za-z]/.test(raw[j])) j += 1;
    if (raw[j] === ';') j += 1;
    let matched = null;
    for (let end = j; end > i; end -= 1) {
      const key = raw.slice(i, end);
      if (Object.prototype.hasOwnProperty.call(input.entities, key)) { matched = { end, value: input.entities[key] }; break; }
    }
    if (!matched) { out += raw.slice(start, Math.max(i, j)); i = Math.max(i, j); continue; }
    out += matched.value; i = matched.end;
  }
  return out;
}
function decoderElement() {
  let textContent = '', attrValue = null;
  return {
    get textContent() { return textContent; },
    get children() { return attrValue === null ? [] : [{ getAttribute(n) { return n === 'foo' ? attrValue : null; } }]; },
    set innerHTML(value) {
      const text = String(value), m = text.match(/^<div foo="([\s\S]*)">$/);
      if (m) { attrValue = decodeEntities(m[1]); textContent = ''; }
      else { attrValue = null; textContent = decodeEntities(text); }
    },
  };
}
const sandbox = { console: { log(){}, info(){}, warn(){}, error(){} }, setTimeout, clearTimeout, setInterval, clearInterval };
vm.createContext(sandbox);
vm.runInContext(vueSource, sandbox, { filename: 'vue-3.5.41.global.js', timeout: 10000 });
sandbox.document = { createElement(tag) { if (String(tag).toLowerCase() !== 'div') throw new Error('unexpected DOM tag: ' + tag); return decoderElement(); } };
const NativeFunction = vm.runInContext('Function', sandbox);
let factories = [];
const WrappedFunction = function(...args) {
  const strings = args.map((x) => String(x));
  if (strings.length === 1 && strings[0].includes('return function render') && strings[0].includes('_Vue') && strings[0].includes('Vue')) factories.push(strings[0]);
  return NativeFunction(...args);
};
WrappedFunction.prototype = NativeFunction.prototype;
sandbox.Function = WrappedFunction;
const out = [];
for (const unit of input.units) {
  factories = [];
  const render = sandbox.Vue.compile(unit.template);
  if (typeof render !== 'function' || factories.length !== 1) throw new Error(unit.name + ': render factory inventory=' + factories.length);
  out.push({ name: unit.name, factory: factories[0], factoryHash: sha(factories[0]) });
}
process.stdout.write(JSON.stringify(out));
'''

payload = json.dumps({'vuePath': str(VUE_ASSET), 'units': units, 'entities': dict(HTML5_ENTITIES)}, ensure_ascii=False)
proc = subprocess.run(['node', '-e', node_compile], input=payload, text=True, capture_output=True, timeout=45, check=False)
if proc.returncode != 0:
    fail('compiler extraction failed: ' + re.sub(r'\s+', ' ', proc.stderr.strip())[:500])
try:
    compiled = json.loads(proc.stdout)
except Exception:
    fail('compiler extraction returned invalid JSON')
if [item.get('name') for item in compiled] != [item['name'] for item in units]:
    fail('compiled factory order drifted')
for item in compiled:
    expected = EXPECTED_FACTORY_HASHES[item['name']]
    if item.get('factoryHash') != expected:
        fail(f"{item['name']} factory hash drift: expected={expected}; actual={item.get('factoryHash')}")

lines = [
    '/* GrowthOps CRM: deterministic Vue 3.5.41 precompiled render registry. */',
    '(function () {',
    '  const renders = Object.freeze({',
]
for idx, item in enumerate(compiled):
    comma = ',' if idx + 1 < len(compiled) else ''
    lines.append(f"    {item['name']}: (function () {{")
    for source_line in item['factory'].splitlines():
        lines.append('      ' + source_line)
    lines.append(f'    }})(){comma}')
lines.extend([
    '  });',
    "  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {",
    '    value: renders, writable: false, configurable: false, enumerable: false',
    '  });',
    '})();',
    '',
])
asset = '\n'.join(lines)
asset_bytes = asset.encode('utf-8')
asset_sha = hashlib.sha256(asset_bytes).hexdigest()
for forbidden in ('new Function(', 'eval(', 'setTimeout("', "setTimeout('"):
    if forbidden in asset:
        fail('generated static registry contains dynamic-code marker: ' + forbidden)
if EXPECTED_ASSET_SHA256 == '__PROBE__':
    fail(f'PIN_REQUIRED: sha256={asset_sha}; bytes={len(asset_bytes)}')
if asset_sha != EXPECTED_ASSET_SHA256 or len(asset_bytes) != EXPECTED_ASSET_BYTES:
    fail(f'asset drift: expected={EXPECTED_ASSET_SHA256}/{EXPECTED_ASSET_BYTES}B; actual={asset_sha}/{len(asset_bytes)}B')

node_smoke = r'''
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = { console: { log(){}, info(){}, warn(){}, error(){} }, setTimeout, clearTimeout, setInterval, clearInterval };
vm.createContext(sandbox);
vm.runInContext(input.vue, sandbox, { timeout: 10000 });
sandbox.Function = function(){ throw new Error('dynamic Function forbidden during static registry init'); };
vm.runInContext(input.asset, sandbox, { timeout: 10000 });
const registry = sandbox.GrowthOpsVueRenders;
const names = ['root','component01','component02','component03','component04'];
if (!registry || names.some((name) => typeof registry[name] !== 'function')) throw new Error('static registry functions missing');
if (!Object.isFrozen(registry)) throw new Error('static registry not frozen');
process.stdout.write('ok');
'''
smoke_payload = json.dumps({'vue': VUE_ASSET.read_text(encoding='utf-8'), 'asset': asset}, ensure_ascii=False)
smoke = subprocess.run(['node', '-e', node_smoke], input=smoke_payload, text=True, capture_output=True, timeout=30, check=False)
if smoke.returncode != 0 or smoke.stdout != 'ok':
    fail('static registry VM smoke failed: ' + re.sub(r'\s+', ' ', smoke.stderr.strip())[:500])

print(
    'VUE_PRECOMPILED_RENDER_ARTIFACT_OK: units=5; vue=3.5.41; '
    f'sha256={asset_sha}; bytes={len(asset_bytes)}; dynamic-code=0; registry=frozen; runtime=unchanged'
)
