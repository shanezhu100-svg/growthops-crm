from html.entities import html5 as HTML5_ENTITIES
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parent
INDEX=ROOT/'dist'/'index.html'
APP_FILES=[ROOT/'dist'/'app'/f'app-inline-{idx:02d}.js' for idx in range(1,4)]
VUE=ROOT/'dist'/'vendor'/'vue-3.5.41.global.js'


def fail(message:str)->None:
    raise SystemExit('VUE_RUNTIME_FINAL_PRECOMPILE_PROBE_FAILED: '+message)


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
summary='; '.join(f"{x['name']}={x['hash']}/{x['bytes']}B" for x in compiled)
fail(f'PIN_REQUIRED: {summary}; registry={asset_sha}/{len(asset_bytes)}B; units=5; dynamic-code=0')
