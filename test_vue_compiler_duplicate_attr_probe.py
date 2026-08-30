from html.parser import HTMLParser
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'


def fail(message: str) -> None:
    raise SystemExit('VUE_COMPILER_DUPLICATE_ATTR_PROBE_FAILED: ' + message)


def extract_root(source: str) -> str:
    starts = [0]
    for match in re.finditer(r'\n', source):
        starts.append(match.end())

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.tag = None
            self.start = None
            self.ends = []
            self.body = None
            self.roots = 0

        def pos(self):
            line, offset = self.getpos()
            return starts[line - 1] + offset

        def handle_starttag(self, tag, attrs):
            if dict(attrs).get('id') == 'app':
                self.roots += 1
                self.tag = tag.lower()
                self.start = self.pos() + len(self.get_starttag_text())

        def handle_endtag(self, tag):
            pos = self.pos()
            if tag.lower() == 'body':
                self.body = pos
            if self.tag and tag.lower() == self.tag and self.start is not None and pos > self.start:
                self.ends.append(pos)

    parser = Parser()
    parser.feed(source)
    parser.close()
    if parser.roots != 1 or parser.start is None or parser.body is None:
        fail('root boundary drift')
    ends = [pos for pos in parser.ends if pos < parser.body]
    if not ends:
        fail('root close boundary drift')
    return source[parser.start:max(ends)]


if not INDEX.is_file():
    fail('dist/index.html missing')
if not shutil.which('npm') or not shutil.which('node'):
    fail('Node/npm missing')
template = extract_root(INDEX.read_text(encoding='utf-8'))

with tempfile.TemporaryDirectory(prefix='growthops-vue-compiler-diag-') as raw_tmp:
    tmp = Path(raw_tmp)
    install = subprocess.run(
        ['npm', 'install', '--prefix', str(tmp), '--ignore-scripts', '--no-audit', '--no-fund', '--package-lock=false', '@vue/compiler-dom@3.5.41'],
        text=True, capture_output=True, timeout=120, check=False,
    )
    if install.returncode != 0:
        fail('compiler install failed')
    node = r'''
const fs=require('fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const {compile}=require(input.compiler);
try {
  const result=compile(input.template,{mode:'function',prefixIdentifiers:true,hoistStatic:true,cacheHandlers:false});
  process.stdout.write(JSON.stringify({ok:true,bytes:Buffer.byteLength(result.code||'','utf8')}));
} catch (error) {
  const loc=error&&error.loc&&error.loc.start?error.loc.start:{};
  process.stdout.write(JSON.stringify({ok:false,code:error&&error.code,line:loc.line||0,column:loc.column||0,message:String(error&&error.message||error)}));
}
'''
    payload=json.dumps({'compiler':str(tmp/'node_modules'/'@vue'/'compiler-dom'),'template':template},ensure_ascii=False)
    proc=subprocess.run(['node','-e',node],input=payload,text=True,capture_output=True,timeout=45,check=False)
    if proc.returncode != 0:
        fail('node compiler diagnostic failed: '+re.sub(r'\s+',' ',proc.stderr.strip())[-700:])
    try:
        result=json.loads(proc.stdout)
    except Exception:
        fail('invalid diagnostic JSON')
    if not result.get('ok'):
        line=int(result.get('line') or 0)
        rows=template.splitlines()
        context=rows[line-1].strip() if 1 <= line <= len(rows) else '<line-unavailable>'
        context=re.sub(r'\s+',' ',context)
        fail(
            f"compiler-code={result.get('code')}; line={line}; column={result.get('column')}; "
            f"message={result.get('message')}; source-line={context[:1200]}"
        )

print(f"VUE_COMPILER_DUPLICATE_ATTR_PROBE_OK: strict-prefix-compile=true; code-bytes={result.get('bytes')}")
