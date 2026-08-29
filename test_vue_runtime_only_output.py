from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parent
DIST=ROOT/'dist'
INDEX=DIST/'index.html'
APP_FILES=[DIST/'app'/f'app-inline-{idx:02d}.js' for idx in range(1,4)]
RUNTIME=DIST/'vendor'/'vue-3.5.41.runtime.global.js'
REGISTRY=DIST/'vendor'/'vue-3.5.41.renders.js'
COMPILER=DIST/'vendor'/'vue-3.5.41.global.js'
RUNTIME_SHA='45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088'; RUNTIME_BYTES=414799
REGISTRY_SHA='d91a71ac97b904f27b0a4bf8527473e525ed311635eb1bdcd04ebf95c882658e'; REGISTRY_BYTES=1185796

def fail(m): raise SystemExit('VUE_RUNTIME_ONLY_OUTPUT_FAILED: '+m)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for p in [INDEX,RUNTIME,REGISTRY,*APP_FILES]:
 if not p.is_file(): fail('missing '+str(p.relative_to(ROOT)))
if COMPILER.exists(): fail('compiler-inclusive Vue remains in deploy output')
if (digest(RUNTIME),RUNTIME.stat().st_size)!=(RUNTIME_SHA,RUNTIME_BYTES): fail('runtime-only asset drift')
if (digest(REGISTRY),REGISTRY.stat().st_size)!=(REGISTRY_SHA,REGISTRY_BYTES): fail('render registry drift')
runtime=RUNTIME.read_text(encoding='utf-8'); registry=REGISTRY.read_text(encoding='utf-8')
for marker in ('function compileToFunction(','const compile = compileToFunction','new Function(code)'):
 if marker in runtime: fail('compiler marker in runtime asset: '+marker)
for marker in ('new Function(','eval(','setTimeout("',"setTimeout('"):
 if marker in registry: fail('dynamic-code marker in registry: '+marker)

html=INDEX.read_text(encoding='utf-8')
class ScriptInventory(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=False); self.srcs=[]; self.inline=0
 def handle_starttag(self,tag,attrs):
  if tag.lower()!='script': return
  src=dict(attrs).get('src')
  if src: self.srcs.append(src)
  else: self.inline+=1
parser=ScriptInventory(); parser.feed(html); parser.close()
if parser.inline!=0: fail(f'inline script blocks returned: {parser.inline}')
runtime_src='/vendor/vue-3.5.41.runtime.global.js'; registry_src='/vendor/vue-3.5.41.renders.js'
app_srcs=[f'/app/app-inline-{idx:02d}.js' for idx in range(1,4)]
for src in [runtime_src,registry_src,*app_srcs]:
 if parser.srcs.count(src)!=1: fail(f'script src multiplicity drift: {src}={parser.srcs.count(src)}')
if not (parser.srcs.index(runtime_src)<parser.srcs.index(registry_src)<parser.srcs.index('/app/app-inline-03.js')):
 fail('runtime/registry/Vue-bootstrap execution order drift')
if '/vendor/vue-3.5.41.global.js' in parser.srcs or 'vue-3.5.41.global.js' in html:
 fail('compiler-inclusive script reference remains')

app='\n'.join(p.read_text(encoding='utf-8') for p in APP_FILES)
if re.search(r'(?<![\w$])template\s*:',app): fail('Vue template option remains in shipped app JS')
if app.count('GrowthOpsVueRenders.root')!=1: fail('root render reference drift')
for idx in range(1,5):
 if app.count(f'GrowthOpsVueRenders.component{idx:02d}')!=1: fail(f'component{idx:02d} render reference drift')
for marker in ('new Function(','eval('):
 if marker in app: fail('dynamic code in shipped app JS: '+marker)

cfg=json.loads((ROOT/'vercel.json').read_text(encoding='utf-8')); csp=''
for rule in cfg.get('headers',[]):
 if rule.get('source')=='/(.*)':
  for item in rule.get('headers',[]):
   if item.get('key')=='Content-Security-Policy': csp=item.get('value','')
script=csp.split('script-src ',1)[1].split(';',1)[0].split() if 'script-src ' in csp else []
if script != ["'self'"] or "'unsafe-eval'" in csp or "'unsafe-inline'" in csp: fail('final CSP is not same-origin/eval-free')

smoke_js=r'''
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));const sandbox={console:{log(){},info(){},warn(){},error(){}},setTimeout,clearTimeout,setInterval,clearInterval};vm.createContext(sandbox);vm.runInContext(input.runtime,sandbox,{timeout:10000});sandbox.Function=function(){throw Error('dynamic Function forbidden');};vm.runInContext(input.registry,sandbox,{timeout:10000});const r=sandbox.GrowthOpsVueRenders;if(!r||!Object.isFrozen(r)||typeof r.root!=='function')throw Error('registry invalid');for(const k of ['component01','component02','component03','component04'])if(typeof r[k]!=='function')throw Error(k+' missing');const app=sandbox.Vue.createApp({render:r.root});if(!app||typeof app.mount!=='function')throw Error('runtime createApp failed');process.stdout.write('ok');
'''
smoke=subprocess.run(['node','-e',smoke_js],input=json.dumps({'runtime':runtime,'registry':registry}),text=True,capture_output=True,timeout=30,check=False)
if smoke.returncode!=0 or smoke.stdout!='ok': fail('runtime-only VM smoke failed: '+re.sub(r'\s+',' ',smoke.stderr.strip())[:400])
print(f'VUE_RUNTIME_ONLY_OUTPUT_OK: runtime={RUNTIME_SHA}/{RUNTIME_BYTES}B; registry={REGISTRY_SHA}/{REGISTRY_BYTES}B; renders=5; template-options=0; compiler=absent; CSP=self-only+eval-free; inline-scripts=0; vm-smoke=pass')
