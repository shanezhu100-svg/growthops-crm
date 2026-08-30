from html.entities import html5 as HTML5_ENTITIES
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]
VUE_ASSET = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'

EXPECTED = {
    'root': {
        'templateHash': '1da528f35f324c08987065cc734bccf2b0cd948b47cd880e66ebc5ed85fbc5f3',
        'templateBytes': 355190,
        'renderHash': '416835ec9c00f34f2018bf8bc771e2d3b4beedf048b9913b64dc152aeb3c6683',
        'renderBytes': 958346,
        'factoryHash': 'a50d08721462a90906440c5a351caedf24a871fd794ad4b9eb0dfb5c2adcdb9e',
        'factoryBytes': 1095423,
        'functionCalls': 2157,
    },
    'component-01': {
        'templateHash': '2f51f5b5ec5ef5bbe12bac62b317a4ad4154cb545779ef8cecb908d016642088',
        'templateBytes': 461,
        'renderHash': 'aefa412f1389fda22ae6e635dce71af56c157e6d511b17a5253e82d4999df06d',
        'renderBytes': 1019,
        'factoryHash': '12ce20f7003c90017ebf8cd31e97bc632eb90518176775dbfe663c9b9166fae6',
        'factoryBytes': 1550,
        'functionCalls': 3,
    },
    'component-02': {
        'templateHash': 'f53ef37adfd6f610d2419ab6872195fed96961e80706d572341c923643f7e3f8',
        'templateBytes': 196,
        'renderHash': '12c2efed40fa60a06daf32a6461bbb7b662219641983820d2ea60bc6ba81057e',
        'renderBytes': 469,
        'factoryHash': '7a99ecc1e3f6f9d2d14501681e630c40fa59f94144a50d72f392aa757732dcd7',
        'factoryBytes': 756,
        'functionCalls': 3,
    },
    'component-03': {
        'templateHash': 'abceefaa3412391b9b1d384e543144f7b8e2fa30384b9cfd38b1cbb09aeaa788',
        'templateBytes': 126,
        'renderHash': 'e512d811d2b8687f9292c7d39478171b4da4184d19938eb24bf779f39ad33ba8',
        'renderBytes': 439,
        'factoryHash': '658b8af682a2023c6e01515def82b39f1fcaf5fe7a7315c582e298ff0c3a85be',
        'factoryBytes': 646,
        'functionCalls': 2,
    },
    'component-04': {
        'templateHash': 'c761ce8b7a5d43b432bedbc10082909bd3eba1add514f37d73802226c1275de4',
        'templateBytes': 1936,
        'renderHash': 'ec3ee231619a12837af224d776070bc250afa2e484ecefd4c32a46295635d9a4',
        'renderBytes': 3610,
        'factoryHash': '0ca46a8239700de84f36e527fc8bef3d737fdb09fb78fa64c5242a9ba4d8bb87',
        'factoryBytes': 4776,
        'functionCalls': 23,
    },
}


def fail(message: str) -> None:
    raise SystemExit('VUE_PRECOMPILE_FEASIBILITY_FAILED: ' + message)


def extract_app_inner_html(source: str) -> str:
    line_starts = [0]
    for match in re.finditer(r'\n', source):
        line_starts.append(match.end())

    class AppExtractor(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.root_tag = None
            self.inner_start = None
            self.root_end_positions = []
            self.body_end = None
            self.roots = 0

        def absolute_pos(self) -> int:
            line, offset = self.getpos()
            return line_starts[line - 1] + offset

        def handle_starttag(self, tag, attrs):
            if dict(attrs).get('id') != 'app':
                return
            self.roots += 1
            if self.roots != 1:
                fail('multiple #app roots found')
            self.root_tag = tag.lower()
            self.inner_start = self.absolute_pos() + len(self.get_starttag_text())

        def handle_startendtag(self, tag, attrs):
            if dict(attrs).get('id') == 'app':
                fail('#app root cannot be self-closing')

        def handle_endtag(self, tag):
            low = tag.lower()
            pos = self.absolute_pos()
            if low == 'body':
                self.body_end = pos
            if self.root_tag and low == self.root_tag and self.inner_start is not None and pos > self.inner_start:
                self.root_end_positions.append(pos)

    parser = AppExtractor()
    parser.feed(source)
    parser.close()
    if parser.roots != 1 or parser.inner_start is None or not parser.root_tag:
        fail('root #app opening element not found exactly once')
    if parser.body_end is None or parser.body_end <= parser.inner_start:
        fail('body closing boundary not found after #app root')
    candidate_ends = [pos for pos in parser.root_end_positions if pos < parser.body_end]
    if not candidate_ends:
        fail('root #app closing element not found before body boundary')
    template = source[parser.inner_start:max(candidate_ends)]
    if len(template.encode('utf-8')) < 100_000:
        fail('root template unexpectedly small')
    if 'id="app"' in template or "id='app'" in template:
        fail('nested duplicate #app marker found inside extracted template')
    return template


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
component_templates = extract_template_literals(app_js)
if len(component_templates) != 4:
    fail(f'expected 4 component template literals, found {len(component_templates)}')
units = [{'name': 'root', 'template': extract_app_inner_html(html)}]
units.extend({'name': f'component-{idx:02d}', 'template': tpl} for idx, tpl in enumerate(component_templates, 1))

node_probe = r'''
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
      const digitsStart = j;
      while (j < raw.length && (radix === 16 ? /[0-9A-Fa-f]/.test(raw[j]) : /[0-9]/.test(raw[j]))) j += 1;
      if (j === digitsStart) { out += '&'; continue; }
      const value = Number.parseInt(raw.slice(digitsStart, j), radix);
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
function makeDecoderElement() {
  let textContent = '', attrValue = null;
  return {
    get textContent() { return textContent; },
    get children() { return attrValue === null ? [] : [{ getAttribute(name) { return name === 'foo' ? attrValue : null; } }]; },
    set innerHTML(value) {
      const text = String(value), match = text.match(/^<div foo="([\s\S]*)">$/);
      if (match) { attrValue = decodeEntities(match[1]); textContent = ''; }
      else { attrValue = null; textContent = decodeEntities(text); }
    },
  };
}
function compilePass() {
  const documentShim = { createElement(tag) {
    if (String(tag).toLowerCase() !== 'div') throw new Error('unexpected document.createElement in compiler probe: ' + tag);
    return makeDecoderElement();
  }};
  const sandbox = { console: { log(){}, info(){}, warn(){}, error(){} }, setTimeout, clearTimeout, setInterval, clearInterval };
  vm.createContext(sandbox);
  vm.runInContext(vueSource, sandbox, { filename: 'vue-3.5.41.global.js', timeout: 10000 });
  if (!sandbox.Vue || typeof sandbox.Vue.compile !== 'function') throw new Error('Vue.compile unavailable');
  sandbox.document = documentShim;
  const NativeFunction = vm.runInContext('Function', sandbox);
  let captureCount = 0, renderFactories = [];
  const WrappedFunction = function(...args) {
    const strings = args.map((arg) => String(arg));
    captureCount += 1;
    if (strings.length === 1 && strings[0].includes('return function render') && strings[0].includes('_Vue') && strings[0].includes('Vue')) renderFactories.push(strings[0]);
    return NativeFunction(...args);
  };
  WrappedFunction.prototype = NativeFunction.prototype;
  sandbox.Function = WrappedFunction;
  const out = [];
  for (const unit of input.units) {
    captureCount = 0; renderFactories = [];
    const render = sandbox.Vue.compile(unit.template);
    if (typeof render !== 'function') throw new Error(unit.name + ': compile did not return function');
    if (renderFactories.length !== 1) throw new Error(unit.name + ': expected one render factory capture, found ' + renderFactories.length + '; total Function calls=' + captureCount);
    const factory = renderFactories[0], renderSource = Function.prototype.toString.call(render);
    out.push({ name: unit.name, templateBytes: Buffer.byteLength(unit.template, 'utf8'), templateHash: sha(unit.template), renderBytes: Buffer.byteLength(renderSource, 'utf8'), renderHash: sha(renderSource), functionCalls: captureCount, factoryBytes: Buffer.byteLength(factory, 'utf8'), factoryHash: sha(factory) });
  }
  return out;
}
const first = compilePass(), second = compilePass();
process.stdout.write(JSON.stringify({ first, second }));
'''

payload = json.dumps({'vuePath': str(VUE_ASSET), 'units': units, 'entities': dict(HTML5_ENTITIES)}, ensure_ascii=False)
try:
    proc = subprocess.run(['node', '-e', node_probe], input=payload, text=True, capture_output=True, timeout=45, check=False)
except Exception as exc:
    fail('node probe launch failed: ' + type(exc).__name__)
if proc.returncode != 0:
    fail('node probe failed rc=' + str(proc.returncode) + ': ' + re.sub(r'\s+', ' ', proc.stderr.strip())[:700])
try:
    result = json.loads(proc.stdout)
except Exception:
    fail('node probe returned invalid JSON')
first, second = result.get('first'), result.get('second')
if not isinstance(first, list) or not isinstance(second, list) or len(first) != 5 or len(second) != 5:
    fail('unexpected compile result inventory')
if first != second:
    fail('compiler output is not deterministic across isolated VM passes')
if {item.get('name') for item in first} != set(EXPECTED):
    fail('compiled unit names drifted')

fields = ('templateHash', 'templateBytes', 'renderHash', 'renderBytes', 'factoryHash', 'factoryBytes', 'functionCalls')
for item in first:
    name = item['name']
    actual = {field: item.get(field) for field in fields}
    if actual != EXPECTED[name]:
        fail(f'{name} deterministic compiler evidence drifted: expected={EXPECTED[name]}; actual={actual}')

print(
    'VUE_PRECOMPILE_FEASIBILITY_OK: units=5; deterministic=2-vm-pass; '
    'root-factory=a50d08721462/1095423B; components=4; full-template+render+factory-hashes=pinned; '
    'compiler-Function-call-inventory=pinned; runtime=unchanged'
)
