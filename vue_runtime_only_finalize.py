from html.entities import html5 as HTML5_ENTITIES
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parent
DIST=ROOT/'dist'
INDEX=DIST/'index.html'
APP_FILES=[DIST/'app'/f'app-inline-{idx:02d}.js' for idx in range(1,4)]
COMPILER=DIST/'vendor'/'vue-3.5.41.global.js'
RUNTIME=DIST/'vendor'/'vue-3.5.41.runtime.global.js'
REGISTRY=DIST/'vendor'/'vue-3.5.41.renders.js'
RUNTIME_URL='https://unpkg.com/vue@3.5.41/dist/vue.runtime.global.js'
RUNTIME_SHA='45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088'
RUNTIME_BYTES=414799
EXPECTED_TEMPLATES={
 'root':('6a4b1cddf1e55886910b59c914cba446ba0cf3300551f22f8d332dbe6d971385',355148),
 'component01':('2f51f5b5ec5ef5bbe12bac62b317a4ad4154cb545779ef8cecb908d016642088',461),
 'component02':('f53ef37adfd6f610d2419ab6872195fed96961e80706d572341c923643f7e3f8',196),
 'component03':('abceefaa3412391b9b1d384e543144f7b8e2fa30384b9cfd38b1cbb09aeaa788',126),
 'component04':('c761ce8b7a5d43b432bedbc10082909bd3eba1add514f37d73802226c1275de4',1936),
}
EXPECTED_FACTORIES={
 'root':('a71d8e3fd7fe3a673f939aadcc37a3ab18b3fe9aa97b65d2ca4a5fd1bdcb0c52',1095257),
 'component01':('12ce20f7003c90017ebf8cd31e97bc632eb90518176775dbfe663c9b9166fae6',1550),
 'component02':('7a99ecc1e3f6f9d2d14501681e630c40fa59f94144a50d72f392aa757732dcd7',756),
 'component03':('658b8af682a2023c6e01515def82b39f1fcaf5fe7a7315c582e298ff0c3a85be',646),
 'component04':('0ca46a8239700de84f36e527fc8bef3d737fdb09fb78fa64c5242a9ba4d8bb87',4776),
}
REGISTRY_SHA='36f6a36bf0793c8713ad0f3788d4f223a422cb9832d3c5f061ff32a695f2fc0d'
REGISTRY_BYTES=1185809


def fail(message:str)->None: raise SystemExit('VUE_RUNTIME_ONLY_FINALIZE_FAILED: '+message)
def sha(data:bytes)->str: return hashlib.sha256(data).hexdigest()
def sha_text(text:str)->str: return sha(text.encode('utf-8'))

def extract_root(source:str)->str:
 starts=[0]
 for m in re.finditer(r'\n',source): starts.append(m.end())
 class P(HTMLParser):
  def __init__(self): super().__init__(convert_charrefs=False); self.tag=None; self.start=None; self.ends=[]; self.body=None; self.n=0
  def pos(self): line,off=self.getpos(); return starts[line-1]+off
  def handle_starttag(self,tag,attrs):
   if dict(attrs).get('id')!='app': return
   self.n+=1; self.tag=tag.lower(); self.start=self.pos()+len(self.get_starttag_text())
  def handle_endtag(self,tag):
   p=self.pos(); low=tag.lower()
   if low=='body': self.body=p
   if self.tag and low==self.tag and self.start is not None and p>self.start: self.ends.append(p)
 p=P(); p.feed(source); p.close()
 if p.n!=1 or p.start is None or p.body is None: fail('root boundary drift')
 ends=[x for x in p.ends if x<p.body]
 if not ends: fail('root closing boundary drift')
 return source[p.start:max(ends)]

def template_entries(source:str):
 out=[]; marker=re.compile(r'(?<![\w$])template\s*:\s*`')
 for m in marker.finditer(source):
  i=m.end(); start=i; escaped=False
  while i<len(source):
   ch=source[i]
   if ch=='`' and not escaped:
    out.append((m.start(),i+1,source[start:i])); break
   escaped=(ch=='\\' and not escaped)
   if ch!='\\': escaped=False
   i+=1
  else: fail('unterminated component template')
 return out

# Apply the narrowly scoped finance correction before the final Vue render registry
# is generated. This keeps the shipped application JS and its precompiled runtime
# materialization on the same byte authority for downstream browser regressions.
import finance_confirmed_profit_cost_finalize  # noqa: E402,F401

for p in [INDEX,COMPILER,*APP_FILES]:
 if not p.is_file(): fail('missing '+str(p.relative_to(ROOT)))
html=INDEX.read_text(encoding='utf-8')
blocks=[p.read_text(encoding='utf-8') for p in APP_FILES]
entries=[template_entries(b) for b in blocks]
if [len(x) for x in entries] != [0,0,4]: fail('component template layout drifted')
root=extract_root(html)
units=[{'name':'root','template':root}]+[{'name':f'component{i:02d}','template':e[2]} for i,e in enumerate(entries[2],1)]
for u in units:
 expected=EXPECTED_TEMPLATES[u['name']]; actual=(sha_text(u['template']),len(u['template'].encode('utf-8')))
 if actual!=expected: fail(f"{u['name']} template drift: expected={expected[0]}/{expected[1]}B; actual={actual[0]}/{actual[1]}B")

node=r'''
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');const input=JSON.parse(fs.readFileSync(0,'utf8'));const src=fs.readFileSync(input.vue,'utf8');const sh=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
function decode(raw){let out='';for(let i=0;i<raw.length;){if(raw[i]!=='&'){out+=raw[i++];continue;}const start=i++;if(raw[i]==='#'){let j=i+1,radix=10;if(raw[j]==='x'||raw[j]==='X'){radix=16;j++;}const ds=j;while(j<raw.length&&(radix===16?/[0-9A-Fa-f]/.test(raw[j]):/[0-9]/.test(raw[j])))j++;if(j===ds){out+='&';continue;}const value=parseInt(raw.slice(ds,j),radix);if(raw[j]===';')j++;out+=String.fromCodePoint(value>0&&value<=0x10ffff?value:0xfffd);i=j;continue;}let j=i;while(j<raw.length&&/[0-9A-Za-z]/.test(raw[j]))j++;if(raw[j]===';')j++;let hit=null;for(let end=j;end>i;end--){const key=raw.slice(i,end);if(Object.prototype.hasOwnProperty.call(input.entities,key)){hit={end,value:input.entities[key]};break;}}if(!hit){out+=raw.slice(start,Math.max(i,j));i=Math.max(i,j);continue;}out+=hit.value;i=hit.end;}return out;}
function decoder(){let text='',attr=null;return{get textContent(){return text;},get children(){return attr===null?[]:[{getAttribute(n){return n==='foo'?attr:null;}}];},set innerHTML(v){const s=String(v),m=s.match(/^<div foo="([\s\S]*)">$/);if(m){attr=decode(m[1]);text='';}else{attr=null;text=decode(s);}}};}
const sandbox={console:{log(){},info(){},warn(){},error(){}},setTimeout,clearTimeout,setInterval,clearInterval};vm.createContext(sandbox);vm.runInContext(src,sandbox,{timeout:10000});sandbox.document={createElement(tag){if(String(tag).toLowerCase()!=='div')throw Error('unexpected tag');return decoder();}};const Native=vm.runInContext('Function',sandbox);let factories=[];const Wrapped=function(...args){const ss=args.map(String);if(ss.length===1&&ss[0].includes('return function render')&&ss[0].includes('_Vue'))factories.push(ss[0]);return Native(...args);};Wrapped.prototype=Native.prototype;sandbox.Function=Wrapped;const out=[];for(const u of input.units){factories=[];const render=sandbox.Vue.compile(u.template);if(typeof render!=='function'||factories.length!==1)throw Error(u.name+': factories='+factories.length);out.push({name:u.name,factory:factories[0],hash:sh(factories[0]),bytes:Buffer.byteLength(factories[0])});}process.stdout.write(JSON.stringify(out));
'''
payload=json.dumps({'vue':str(COMPILER),'units':units,'entities':dict(HTML5_ENTITIES)},ensure_ascii=False)
proc=subprocess.run(['node','-e',node],input=payload,text=True,capture_output=True,timeout=45,check=False)
if proc.returncode!=0: fail('compile failed: '+re.sub(r'\s+',' ',proc.stderr.strip())[:400])
try: compiled=json.loads(proc.stdout)
except Exception: fail('invalid compiler JSON')
for item in compiled:
 expected=EXPECTED_FACTORIES[item['name']]; actual=(item['hash'],item['bytes'])
 if actual!=expected: fail(f"{item['name']} factory drift")
lines=['/* GrowthOps CRM: deterministic Vue 3.5.41 final-stage render registry. */','(function () {','  const renders = Object.freeze({']
for idx,item in enumerate(compiled):
 comma=',' if idx+1<len(compiled) else ''
 lines.append(f"    {item['name']}: (function () {{")
 for line in item['factory'].splitlines(): lines.append('      '+line)
 lines.append(f'    }})(){comma}')
lines.extend(['  });',"  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {",'    value: renders, writable: false, configurable: false, enumerable: false','  });','})();',''])
registry='\n'.join(lines); registry_bytes=registry.encode('utf-8')
if (sha(registry_bytes),len(registry_bytes))!=(REGISTRY_SHA,REGISTRY_BYTES): fail('render registry drift')
for forbidden in ('new Function(','eval(','setTimeout("',"setTimeout('"):
 if forbidden in registry: fail('dynamic code in render registry: '+forbidden)

req=urllib.request.Request(RUNTIME_URL,headers={'User-Agent':'growthops-crm-build/1'})
try:
 with urllib.request.urlopen(req,timeout=90) as resp:
  if resp.geturl()!=RUNTIME_URL: fail('runtime-only redirect: '+resp.geturl())
  runtime=resp.read()
except SystemExit: raise
except Exception as exc: fail('runtime-only download failed: '+type(exc).__name__)
if (sha(runtime),len(runtime))!=(RUNTIME_SHA,RUNTIME_BYTES): fail('runtime-only asset drift')
text=runtime.decode('utf-8')
for forbidden in ('function compileToFunction(','const compile = compileToFunction','new Function(code)'):
 if forbidden in text: fail('runtime-only compiler marker present: '+forbidden)

new_blocks=list(blocks)
repls=[]
for idx,(start,end,tpl) in enumerate(entries[2],1): repls.append((start,end,f'render: GrowthOpsVueRenders.component{idx:02d}'))
for start,end,replacement in reversed(repls): new_blocks[2]=new_blocks[2][:start]+replacement+new_blocks[2][end:]
create=list(re.finditer(r'\b(?:Vue\.)?createApp\s*\(\s*\{',new_blocks[2]))
if len(create)!=1: fail(f'createApp anchor count={len(create)}')
pos=create[0].end(); new_blocks[2]=new_blocks[2][:pos]+'\n  render: GrowthOpsVueRenders.root,'+new_blocks[2][pos:]
if sum(len(template_entries(b)) for b in new_blocks)!=0: fail('component template option remains after rewrite')
if new_blocks[2].count('GrowthOpsVueRenders.root')!=1: fail('root render reference count drifted')
for idx in range(1,5):
 if new_blocks[2].count(f'GrowthOpsVueRenders.component{idx:02d}')!=1: fail(f'component{idx:02d} render reference drifted')
compiler_tag='<script src="/vendor/vue-3.5.41.global.js"></script>'
runtime_tag='<script src="/vendor/vue-3.5.41.runtime.global.js"></script>'
registry_tag='<script src="/vendor/vue-3.5.41.renders.js"></script>'
if html.count(compiler_tag)!=1: fail(f'compiler script tag count={html.count(compiler_tag)}')
new_html=html.replace(compiler_tag,runtime_tag+'\n'+registry_tag,1)
if compiler_tag in new_html or new_html.count(runtime_tag)!=1 or new_html.count(registry_tag)!=1: fail('Vue script rewrite drifted')
if new_html.index(runtime_tag)>new_html.index(registry_tag): fail('runtime must load before registry')
app_tag='<script src="/app/app-inline-03.js"></script>'
if app_tag not in new_html or new_html.index(registry_tag)>new_html.index(app_tag): fail('registry must load before Vue-dependent app bootstrap')

def write_atomic(path:Path,data:bytes):
 tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_bytes(data); os.replace(tmp,path)
write_atomic(RUNTIME,runtime)
write_atomic(REGISTRY,registry_bytes)
for path,content in zip(APP_FILES,new_blocks): write_atomic(path,content.encode('utf-8'))
write_atomic(INDEX,new_html.encode('utf-8'))
COMPILER.unlink()

print(f'VUE_RUNTIME_ONLY_FINALIZE_OK: runtime={RUNTIME_SHA}/{RUNTIME_BYTES}B; registry={REGISTRY_SHA}/{REGISTRY_BYTES}B; renders=root+4; templates=removed; compiler-browser-asset=removed; unsafe-eval-target=absent')
