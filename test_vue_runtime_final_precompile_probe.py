from html.entities import html5 as HTML5_ENTITIES
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parent
INDEX=ROOT/'dist'/'index.html'
APP_FILES=[ROOT/'dist'/'app'/f'app-inline-{idx:02d}.js' for idx in range(1,4)]
VUE=ROOT/'dist'/'vendor'/'vue-3.5.41.global.js'
RUNTIME_URL='https://unpkg.com/vue@3.5.41/dist/vue.runtime.global.js'
RUNTIME_SHA='45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088'
RUNTIME_BYTES=414799
EXPECTED_FACTORIES={
    'root':('4fe173224f3ea60ada057bf39f5b25dfcc1a1bc46a5e3a3d140845aa93eecfe7',1095246),
    'component01':('12ce20f7003c90017ebf8cd31e97bc632eb90518176775dbfe663c9b9166fae6',1550),
    'component02':('7a99ecc1e3f6f9d2d14501681e630c40fa59f94144a50d72f392aa757732dcd7',756),
    'component03':('658b8af682a2023c6e01515def82b39f1fcaf5fe7a7315c582e298ff0c3a85be',646),
    'component04':('0ca46a8239700de84f36e527fc8bef3d737fdb09fb78fa64c5242a9ba4d8bb87',4776),
}
EXPECTED_REGISTRY_SHA='d91a71ac97b904f27b0a4bf8527473e525ed311635eb1bdcd04ebf95c882658e'
EXPECTED_REGISTRY_BYTES=1185796


def fail(message:str)->None:
    raise SystemExit('VUE_RUNTIME_FINAL_PRECOMPILE_FAILED: '+message)


def extract_root(source:str)->str:
    starts=[0]
    for m in re.finditer(r'\n',source): starts.append(m.end())
    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False); self.tag=None; self.start=None; self.ends=[]; self.body=None; self.n=0
        def pos(self):
            line,off=self.getpos(); return starts[line-1]+off
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


def components(source:str)->list[str]:
    out=[]; marker=re.compile(r'(?<![\w$])template\s*:\s*`')
    for m in marker.finditer(source):
        i=m.end(); start=i; escaped=False
        while i<len(source):
            ch=source[i]
            if ch=='`' and not escaped: out.append(source[start:i]); break
            escaped=(ch=='\\' and not escaped)
            if ch!='\\': escaped=False
            i+=1
        else: fail('unterminated template')
    return out

for path in [INDEX,VUE,*APP_FILES]:
    if not path.is_file(): fail('missing '+str(path.relative_to(ROOT)))
html=INDEX.read_text(encoding='utf-8')
app='\n'.join(p.read_text(encoding='utf-8') for p in APP_FILES)
tpls=components(app)
if len(tpls)!=4: fail(f'component count={len(tpls)}')
units=[{'name':'root','template':extract_root(html)}]+[{'name':f'component{i:02d}','template':t} for i,t in enumerate(tpls,1)]

node=r'''
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const input=JSON.parse(fs.readFileSync(0,'utf8')); const src=fs.readFileSync(input.vue,'utf8');
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
function decode(raw){let out='';for(let i=0;i<raw.length;){if(raw[i]!=='&'){out+=raw[i++];continue;}const start=i++;if(raw[i]==='#'){let j=i+1,radix=10;if(raw[j]==='x'||raw[j]==='X'){radix=16;j++;}const ds=j;while(j<raw.length&&(radix===16?/[0-9A-Fa-f]/.test(raw[j]):/[0-9]/.test(raw[j])))j++;if(j===ds){out+='&';continue;}const value=parseInt(raw.slice(ds,j),radix);if(raw[j]===';')j++;out+=String.fromCodePoint(value>0&&value<=0x10ffff?value:0xfffd);i=j;continue;}let j=i;while(j<raw.length&&/[0-9A-Za-z]/.test(raw[j]))j++;if(raw[j]===';')j++;let hit=null;for(let end=j;end>i;end--){const key=raw.slice(i,end);if(Object.prototype.hasOwnProperty.call(input.entities,key)){hit={end,value:input.entities[key]};break;}}if(!hit){out+=raw.slice(start,Math.max(i,j));i=Math.max(i,j);continue;}out+=hit.value;i=hit.end;}return out;}
function decoder(){let text='',attr=null;return{get textContent(){return text;},get children(){return attr===null?[]:[{getAttribute(n){return n==='foo'?attr:null;}}];},set innerHTML(v){const s=String(v),m=s.match(/^<div foo="([\s\S]*)">$/);if(m){attr=decode(m[1]);text='';}else{attr=null;text=decode(s);}}};}
const sandbox={console:{log(){},info(){},warn(){},error(){}},setTimeout,clearTimeout,setInterval,clearInterval};vm.createContext(sandbox);vm.runInContext(src,sandbox,{timeout:10000});sandbox.document={createElement(tag){if(String(tag).toLowerCase()!=='div')throw Error('unexpected tag');return decoder();}};
const Native=vm.runInContext('Function',sandbox);let factories=[];const Wrapped=function(...args){const ss=args.map(String);if(ss.length===1&&ss[0].includes('return function render')&&ss[0].includes('_Vue'))factories.push(ss[0]);return Native(...args);};Wrapped.prototype=Native.prototype;sandbox.Function=Wrapped;
const out=[];for(const u of input.units){factories=[];const render=sandbox.Vue.compile(u.template);if(typeof render!=='function'||factories.length!==1)throw Error(u.name+': factories='+factories.length);out.push({name:u.name,factory:factories[0],hash:sha(factories[0]),bytes:Buffer.byteLength(factories[0])});}process.stdout.write(JSON.stringify(out));
'''
payload=json.dumps({'vue':str(VUE),'units':units,'entities':dict(HTML5_ENTITIES)},ensure_ascii=False)
proc=subprocess.run(['node','-e',node],input=payload,text=True,capture_output=True,timeout=45,check=False)
if proc.returncode!=0: fail('compile failed: '+re.sub(r'\s+',' ',proc.stderr.strip())[:400])
try: compiled=json.loads(proc.stdout)
except Exception: fail('invalid compiler JSON')
if [x['name'] for x in compiled] != [u['name'] for u in units]: fail('unit order drift')
for item in compiled:
    expected=EXPECTED_FACTORIES[item['name']]
    actual=(item['hash'],item['bytes'])
    if actual!=expected: fail(f"{item['name']} factory drift: expected={expected[0]}/{expected[1]}B; actual={actual[0]}/{actual[1]}B")

lines=['/* GrowthOps CRM: deterministic Vue 3.5.41 final-stage render registry. */','(function () {','  const renders = Object.freeze({']
for idx,item in enumerate(compiled):
    comma=',' if idx+1<len(compiled) else ''
    lines.append(f"    {item['name']}: (function () {{")
    for line in item['factory'].splitlines(): lines.append('      '+line)
    lines.append(f'    }})(){comma}')
lines.extend(['  });',"  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {",'    value: renders, writable: false, configurable: false, enumerable: false','  });','})();',''])
asset='\n'.join(lines); asset_bytes=asset.encode('utf-8'); asset_sha=hashlib.sha256(asset_bytes).hexdigest()
for forbidden in ('new Function(','eval(','setTimeout("',"setTimeout('"):
    if forbidden in asset: fail('generated registry dynamic-code marker: '+forbidden)
if (asset_sha,len(asset_bytes))!=(EXPECTED_REGISTRY_SHA,EXPECTED_REGISTRY_BYTES):
    fail(f'registry drift: expected={EXPECTED_REGISTRY_SHA}/{EXPECTED_REGISTRY_BYTES}B; actual={asset_sha}/{len(asset_bytes)}B')

# Re-fetch the exact runtime-only build and prove this final registry initializes
# when dynamic Function is disabled. This verifies the registry does not depend on
# the browser compiler that produced it during the trusted build step.
req=urllib.request.Request(RUNTIME_URL,headers={'User-Agent':'growthops-crm-build/1'})
try:
    with urllib.request.urlopen(req,timeout=90) as response:
        if response.geturl()!=RUNTIME_URL: fail('runtime-only unexpected redirect: '+response.geturl())
        runtime=response.read()
except SystemExit: raise
except Exception as exc: fail('runtime-only download failed: '+type(exc).__name__)
runtime_sha=hashlib.sha256(runtime).hexdigest()
if (runtime_sha,len(runtime))!=(RUNTIME_SHA,RUNTIME_BYTES):
    fail(f'runtime-only drift: expected={RUNTIME_SHA}/{RUNTIME_BYTES}B; actual={runtime_sha}/{len(runtime)}B')
smoke_js=r'''
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const warnings=[];const sandbox={console:{log(){},info(){},error(){},warn(...a){warnings.push(a.map(String).join(' '));}},setTimeout,clearTimeout,setInterval,clearInterval};
vm.createContext(sandbox);vm.runInContext(input.runtime,sandbox,{timeout:10000});
sandbox.Function=function(){throw new Error('dynamic Function forbidden during registry init');};
vm.runInContext(input.registry,sandbox,{timeout:10000});
const r=sandbox.GrowthOpsVueRenders,n=['root','component01','component02','component03','component04'];
if(!r||!Object.isFrozen(r)||n.some(k=>typeof r[k]!=='function'))throw new Error('final registry missing/frozen drift');
if(typeof sandbox.Vue.createApp!=='function')throw new Error('runtime createApp missing');
process.stdout.write('ok');
'''
smoke=subprocess.run(['node','-e',smoke_js],input=json.dumps({'runtime':runtime.decode('utf-8'),'registry':asset}),text=True,capture_output=True,timeout=30,check=False)
if smoke.returncode!=0 or smoke.stdout!='ok': fail('runtime-only registry VM smoke failed: '+re.sub(r'\s+',' ',smoke.stderr.strip())[:400])

summary='; '.join(f"{x['name']}={x['hash']}/{x['bytes']}B" for x in compiled)
print(f'VUE_RUNTIME_FINAL_PRECOMPILE_OK: {summary}; registry={asset_sha}/{len(asset_bytes)}B; runtime-only={runtime_sha}/{len(runtime)}B; units=5; dynamic-code=0; vm-smoke=pass')
