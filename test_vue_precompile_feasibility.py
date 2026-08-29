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


def fail(message: str) -> None:
    raise SystemExit('VUE_PRECOMPILE_FEASIBILITY_FAILED: ' + message)


def extract_app_inner_html(source: str) -> str:
    # HTMLParser identifies real tag source positions without being confused by
    # strings in externalized JavaScript. The Vue DOM template contains markup
    # browsers tolerate but that does not always form a strict same-tag stack for
    # HTMLParser, so use the last real closing tag for the unique #app root before
    # the real </body> boundary. This stays independent of where external scripts
    # are placed (head or body) while still slicing the original source bytes.
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
            attrs_dict = dict(attrs)
            if attrs_dict.get('id') != 'app':
                return
            self.roots += 1
            if self.roots != 1:
                fail('multiple #app roots found')
            self.root_tag = tag.lower()
            self.inner_start = self.absolute_pos() + len(self.get_starttag_text())

        def handle_startendtag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if attrs_dict.get('id') == 'app':
                fail('#app root cannot be self-closing')

        def handle_endtag(self, tag):
            low = tag.lower()
            pos = self.absolute_pos()
            if low == 'body':
                self.body_end = pos
            if self.root_tag and low == self.root_tag:
                if self.inner_start is not None and pos > self.inner_start:
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
    inner_end = max(candidate_ends)
    if inner_end <= parser.inner_start:
        fail('root #app closing element precedes root content')

    template = source[parser.inner_start:inner_end]
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

function decodeEntities(raw) {
  let out = '';
  for (let i = 0; i < raw.length;) {
    if (raw[i] !== '&') {
      out += raw[i++];
      continue;
    }
    const start = i;
    i += 1;
    if (raw[i] === '#') {
      let j = i + 1;
      let radix = 10;
      if (raw[j] === 'x' || raw[j] === 'X') {
        radix = 16;
        j += 1;
      }
      const digitsStart = j;
      while (j < raw.length && (radix === 16 ? /[0-9A-Fa-f]/.test(raw[j]) : /[0-9]/.test(raw[j]))) j += 1;
      if (j === digitsStart) {
        out += '&';
        continue;
      }
      const value = Number.parseInt(raw.slice(digitsStart, j), radix);
      if (raw[j] === ';') j += 1;
      const valid = value > 0 && value <= 0x10ffff && !(value >= 0xd800 && value <= 0xdfff);
      out += String.fromCodePoint(valid ? value : 0xfffd);
      i = j;
      continue;
    }
    let j = i;
    while (j < raw.length && /[0-9A-Za-z]/.test(raw[j])) j += 1;
    if (raw[j] === ';') j += 1;
    let matched = null;
    for (let end = j; end > i; end -= 1) {
      const key = raw.slice(i, end);
      if (Object.prototype.hasOwnProperty.call(input.entities, key)) {
        matched = { end, value: input.entities[key] };
        break;
      }
    }
    if (!matched) {
      out += raw.slice(start, Math.max(i, j));
      i = Math.max(i, j);
      continue;
    }
    out += matched.value;
    i = matched.end;
  }
  return out;
}

function makeDecoderElement() {
  let textContent = '';
  let attrValue = null;
  return {
    get textContent() { return textContent; },
    get children() {
      if (attrValue === null) return [];
      return [{ getAttribute(name) { return name === 'foo' ? attrValue : null; } }];
    },
    set innerHTML(value) {
      const text = String(value);
      const match = text.match(/^<div foo="([\s\S]*)">$/);
      if (match) {
        attrValue = decodeEntities(match[1]);
        textContent = '';
      } else {
        attrValue = null;
        textContent = decodeEntities(text);
      }
    },
  };
}

function compilePass() {
  const documentShim = {
    createElement(tag) {
      if (String(tag).toLowerCase() !== 'div') {
        throw new Error('unexpected document.createElement in compiler probe: ' + tag);
      }
      return makeDecoderElement();
    },
  };
  const sandbox = {
    console: { log(){}, info(){}, warn(){}, error(){} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    document: documentShim,
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

payload = json.dumps(
    {
        'vuePath': str(VUE_ASSET),
        'units': units,
        'entities': dict(HTML5_ENTITIES),
    },
    ensure_ascii=False,
)
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

# First successful compile run is intentionally a fail-closed evidence probe.
# After exact hashes are reviewed, replace this terminal probe with pinned asserts.
raise SystemExit(
    'VUE_PRECOMPILE_FEASIBILITY_PROBE: units=5; deterministic=2-vm-pass; '
    + '; '.join(summary)
)
