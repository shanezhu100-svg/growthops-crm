from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]
EXPECTED_TEMPLATES = {
    'root': ('6a4b1cddf1e55886910b59c914cba446ba0cf3300551f22f8d332dbe6d971385', 355148),
    'component01': ('2f51f5b5ec5ef5bbe12bac62b317a4ad4154cb545779ef8cecb908d016642088', 461),
    'component02': ('f53ef37adfd6f610d2419ab6872195fed96961e80706d572341c923643f7e3f8', 196),
    'component03': ('abceefaa3412391b9b1d384e543144f7b8e2fa30384b9cfd38b1cbb09aeaa788', 126),
    'component04': ('c761ce8b7a5d43b432bedbc10082909bd3eba1add514f37d73802226c1275de4', 1936),
}


def fail(message: str) -> None:
    raise SystemExit('VUE_RUNTIME_FINAL_STAGE_FAILED: ' + message)


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def extract_root(source: str) -> str:
    line_starts=[0]
    for match in re.finditer(r'\n', source): line_starts.append(match.end())
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False); self.root_tag=None; self.inner_start=None; self.root_ends=[]; self.body_end=None; self.roots=0
        def pos(self):
            line, offset=self.getpos(); return line_starts[line-1]+offset
        def handle_starttag(self, tag, attrs):
            if dict(attrs).get('id') != 'app': return
            self.roots += 1
            if self.roots != 1: fail('multiple #app roots')
            self.root_tag=tag.lower(); self.inner_start=self.pos()+len(self.get_starttag_text())
        def handle_endtag(self, tag):
            low=tag.lower(); p=self.pos()
            if low=='body': self.body_end=p
            if self.root_tag and low==self.root_tag and self.inner_start is not None and p>self.inner_start: self.root_ends.append(p)
    parser=Parser(); parser.feed(source); parser.close()
    if parser.roots != 1 or parser.inner_start is None or parser.body_end is None: fail('root/body boundary missing')
    ends=[p for p in parser.root_ends if p<parser.body_end]
    if not ends: fail('root closing boundary missing')
    return source[parser.inner_start:max(ends)]


def extract_component_templates(source: str) -> list[str]:
    out=[]; marker=re.compile(r'(?<![\w$])template\s*:\s*`')
    for match in marker.finditer(source):
        i=match.end(); start=i; escaped=False
        while i<len(source):
            ch=source[i]
            if ch=='`' and not escaped: out.append(source[start:i]); break
            escaped=(ch=='\\' and not escaped)
            if ch!='\\': escaped=False
            i+=1
        else: fail('unterminated component template')
    return out


for path in [INDEX,*APP_FILES]:
    if not path.is_file(): fail('missing build artifact: '+str(path.relative_to(ROOT)))
html=INDEX.read_text(encoding='utf-8')
blocks=[path.read_text(encoding='utf-8') for path in APP_FILES]
app_js='\n'.join(blocks)
components=extract_component_templates(app_js)
if [len(extract_component_templates(block)) for block in blocks] != [0,0,4]: fail('component template file layout drifted')
units=[('root',extract_root(html))]+[(f'component{idx:02d}',tpl) for idx,tpl in enumerate(components,1)]
if len(units) != 5: fail(f'expected 5 render units, found {len(units)}')
for name,tpl in units:
    expected_sha,expected_bytes=EXPECTED_TEMPLATES[name]
    actual_sha=sha_text(tpl); actual_bytes=len(tpl.encode('utf-8'))
    if (actual_sha,actual_bytes) != (expected_sha,expected_bytes):
        fail(f'{name} template drift: expected={expected_sha}/{expected_bytes}B; actual={actual_sha}/{actual_bytes}B')
if len(re.findall(r'\b(?:Vue\.)?createApp\s*\(\s*\{',app_js)) != 1: fail('createApp object-literal anchor drifted')
if len(re.findall(r'\.mount\s*\(',app_js)) != 1: fail('mount multiplicity drifted')
if len(re.findall(r'(?<![\w$])render\s*:',app_js)) != 0: fail('render option already exists before migration')
if re.search(r'\sstyle\s*=\s*[\"\']',html,flags=re.I): fail('final HTML style attribute returned')
if re.search(r'\.style(?:\.|\[)|\.setAttribute\s*\(\s*[\"\']style[\"\']',app_js): fail('final app style sink returned')

print('VUE_RUNTIME_FINAL_STAGE_OK: templates=5-pinned; component-layout=0+0+4; createApp=object-literal-single; mount=single; render-options=0; style-sinks=0')

import test_vue_runtime_final_precompile_probe  # noqa: F401,E402
