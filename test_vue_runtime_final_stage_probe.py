from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_FILES = [ROOT / 'dist' / 'app' / f'app-inline-{idx:02d}.js' for idx in range(1, 4)]


def fail(message: str) -> None:
    raise SystemExit('VUE_RUNTIME_FINAL_STAGE_PROBE_FAILED: ' + message)


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


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
    return source[parser.inner_start:max(ends)]


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


for path in [INDEX, *APP_FILES]:
    if not path.is_file():
        fail('missing build artifact: ' + str(path.relative_to(ROOT)))
html = INDEX.read_text(encoding='utf-8')
blocks = [path.read_text(encoding='utf-8') for path in APP_FILES]
app_js = '\n'.join(blocks)
root = extract_root(html)
components = extract_component_templates(app_js)
if len(components) != 4:
    fail(f'expected 4 final-stage component templates, found {len(components)}')

create_matches = []
mount_matches = []
file_template_counts = []
for path, block in zip(APP_FILES, blocks):
    create = re.findall(r'\bVue\.createApp\s*\(\s*([A-Za-z_$][\w$]*|\{)', block)
    if create:
        create_matches.extend((path.name, arg) for arg in create)
    mount = re.findall(r'\b([A-Za-z_$][\w$]*)\.mount\s*\(\s*[\"\']#app[\"\']\s*\)', block)
    if mount:
        mount_matches.extend((path.name, name) for name in mount)
    file_template_counts.append((path.name, len(extract_component_templates(block))))

units = [('root', root)] + [(f'component{idx:02d}', tpl) for idx, tpl in enumerate(components, 1)]
unit_summary = '; '.join(
    f'{name}={sha_text(template)}/{len(template.encode("utf-8"))}B'
    for name, template in units
)
layout = ','.join(f'{name}:{count}' for name, count in file_template_counts)

problems = []
if len(create_matches) != 1:
    problems.append('createApp=' + repr(create_matches))
if len(mount_matches) != 1:
    problems.append('mount=' + repr(mount_matches))
render_count = len(re.findall(r'(?<![\w$])render\s*:', app_js))
if render_count != 0:
    problems.append(f'render-options={render_count}')
if re.search(r'\sstyle\s*=\s*[\"\']', html, flags=re.I):
    problems.append('html-style-attr-present')
if re.search(r'\.style(?:\.|\[)|\.setAttribute\s*\(\s*[\"\']style[\"\']', app_js):
    problems.append('app-style-sink-present')

create_desc = 'unknown'
if len(create_matches) == 1:
    create_file, create_arg = create_matches[0]
    create_desc = f'{create_file}:arg={create_arg}'
mount_desc = 'unknown'
if len(mount_matches) == 1:
    mount_file, mount_receiver = mount_matches[0]
    mount_desc = f'{mount_file}:{mount_receiver}.mount(#app)'

fail(
    'PIN_REQUIRED: '
    + unit_summary
    + f'; component-layout={layout}; createApp={create_desc}; mount={mount_desc}; '
    + f'render-options={render_count}; final-style-sinks={0 if not problems or all("style" not in p for p in problems) else "drift"}; '
    + ('anchor-problems=' + '|'.join(problems) if problems else 'anchors=ready')
)
