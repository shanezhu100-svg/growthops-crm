from pathlib import Path
import hashlib, json, re, shutil

root = Path(__file__).resolve().parent
srcdir = root / '.final-page-canonical'
TARGET_BYTES = 643031
TARGET_SHA256 = '51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43'
pat = re.compile(r'offset-(\d+)-(\d+)\.htmlpart$')

parts = []
for p in srcdir.iterdir():
    m = pat.fullmatch(p.name)
    if not m:
        continue
    start, end = map(int, m.groups())
    raw = p.read_bytes()
    if end <= start or len(raw) != end - start:
        raise SystemExit(f'Invalid canonical chunk: {p.name}')
    parts.append((start, end, p, raw))

parts.sort(key=lambda x: (x[0], x[1]))
pos = 0
raw = bytearray()
for start, end, p, chunk in parts:
    if start != pos:
        kind = 'overlap' if start < pos else 'gap'
        raise SystemExit(f'Canonical source {kind}: expected {pos}, got {start} ({p.name})')
    raw.extend(chunk)
    pos = end

if pos != TARGET_BYTES:
    raise SystemExit(f'Canonical source incomplete: {pos} != {TARGET_BYTES}')
digest = hashlib.sha256(raw).hexdigest()
if digest != TARGET_SHA256:
    raise SystemExit(f'Canonical source SHA mismatch: {digest} != {TARGET_SHA256}')

html = bytes(raw).decode('utf-8')
legacy = (root / 'index.html').read_text(encoding='utf-8')
url = re.search(r"const SUPABASE_URL='([^']+)'", legacy)
key = re.search(r"const API_KEY='([^']+)'", legacy)
if not url or not key:
    raise SystemExit('Existing browser-safe Supabase config not found')

def replace_once(old, new, label):
    global html
    count = html.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    html = html.replace(old, new, 1)

if html.count('createApp({') != 1:
    raise SystemExit('Unexpected Vue app bootstrap count')
html = html.replace('createApp({', 'window.__growthOpsVm=createApp({', 1)

# Preserve the user's approved UI while removing only the four pointer glyphs.
lead_pointer_icons = (
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-slate-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-amber-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-cyan-300"></i>',
    '<i class="fa-solid fa-arrow-pointer text-[9px] text-emerald-300"></i>',
)
for icon in lead_pointer_icons:
    if html.count(icon) != 1:
        raise SystemExit(f'Unexpected lead pointer icon count: {icon}')
    html = html.replace(icon, '', 1)

# Server user editing keeps the password when the field is left blank.
replace_once(
    '<input v-model="userForm.password" required type="password" autocomplete="new-password" class="field" />',
    '<input v-model="userForm.password" :required="!userForm.id" type="password" autocomplete="new-password" class="field" :placeholder="userForm.id?\'留空表示保留原密码\':\'至少 10 位\'" />',
    'user password field'
)
replace_once(
    '当前为单文件演示版，密码保存在浏览器本地。正式上线必须改用服务器认证、哈希密码与数据库。',
    '账号与权限由服务器管理，密码仅以哈希形式保存；编辑用户时密码留空表示保留原密码。',
    'user security notice'
)

# Correct production-only explanatory copy; layout/classes are untouched.
copy_replacements = (
    ('④ 登录角色、页面权限、操作审计和全量数据备份。当前单文件版仍是本地数据仓库，正式上线可无缝替换为服务器数据库。',
     '④ 登录角色、页面权限、操作审计和全量数据备份。正式版业务数据同步至 Supabase 云端数据库。', 'system intro'),
    ('会话仅保存在当前浏览器', '登录令牌保存在当前浏览器，业务数据同步云端', 'session note'),
    ('最多保留最近 5 个本地快照', '最多保留最近 5 个云端快照', 'snapshot count note'),
    ('当前仍是单机 HTML 版本。系统已做页面权限、敏感凭证隐藏、审计日志、月结锁定和备份容量保护；真正多人协作时仍应迁移到后端数据库与服务端登录认证，避免浏览器本地数据被直接读取。',
     '正式版已连接 Supabase 云端数据库与服务端登录认证，并保留页面权限、敏感凭证隐藏、审计日志、月结锁定和数据备份保护。', 'security production note'),
    ('本地数据快照', '云端数据快照', 'snapshot heading'),
)
for old, new, label in copy_replacements:
    replace_once(old, new, label)

# P0 production hardening: remove the reset-demo UI control from production output.
# Runtime access is independently disabled by cloud-p0-overrides.js.
reset_button = re.compile(r'<button\b(?=[^>]*@click=["\']resetDemoData\(\)["\'])[^>]*>.*?</button>', re.S)
html, reset_count = reset_button.subn('', html)
if reset_count not in (0, 1):
    raise SystemExit(f'Unexpected reset-demo UI count: {reset_count}')

# The canonical page's original mounted() loads seed/localStorage data. In production
# it must initialize only UI state/listeners; cloud-adapter.js owns auth and business data.
start = html.index('\n  mounted(){')
end = html.index("\n}).mount('#app');", start)
safe_mounted = r'''
  mounted(){
    this.form=this.defaultForm();
    this.leadForm=this.defaultLeadForm();
    this.openingForm=this.defaultOpeningForm();
    this.providerForm=this.defaultProviderForm();
    this.toolForm=this.defaultToolForm();
    this.receivableForm=this.defaultReceivableForm();
    this.costForm=this.defaultCostForm();
    this.reconciliationForm=this.defaultReconciliationForm();
    this.userForm={id:null,name:'',username:'',password:'',role:'OPS',enabled:true};
    this.updateStorageUsage();
    const allowed=['dashboard','leads','clients','account-opening','alerts','assets','sop','ads','analytics','finance','tools','system','client-detail','client-form'];
    window.addEventListener('hashchange',()=>{
      const h=window.location.hash.slice(1);
      if(this.currentUser&&allowed.includes(h)&&this.canViewPage(h)){
        this.currentPage=h;
        if(h==='analytics')this.syncAnalyticsAccountSelection();
        if(h==='ads')this.syncAdsAccountSelection();
        if(h==='sop')this.syncSopAccountSelection();
      }
    });
    window.addEventListener('beforeunload',(e)=>{if(this.formDirty){e.preventDefault();e.returnValue=''}});
  }'''
html = html[:start] + safe_mounted + html[end:]

config = (
    '<script>'
    f'window.__GROWTHOPS_SUPABASE_URL__={json.dumps(url.group(1))};'
    f'window.__GROWTHOPS_SUPABASE_KEY__={json.dumps(key.group(1))};'
    '</script>'
)
if html.count('</body>') != 1:
    raise SystemExit('Unexpected HTML body ending')
html = html.replace(
    '</body>',
    config + '<script src="/cloud-p1-overrides.js"></script><script src="/cloud-adapter.js"></script><script src="/cloud-p0-overrides.js"></script></body>',
    1
)

p0dir = root / '.p0-overrides-chunks'
p0parts = sorted(p0dir.glob('part-*.bin'))
if not p0parts:
    raise SystemExit('P0 override chunks not found')
p0raw = b''.join(p.read_bytes() for p in p0parts)
P0_BYTES = 33997
P0_SHA256 = '96aebe67255397475092b794281d55375f709e74b549955ea57741600f90442f'
if len(p0raw) != P0_BYTES:
    raise SystemExit(f'P0 override size mismatch: {len(p0raw)} != {P0_BYTES}')
p0digest = hashlib.sha256(p0raw).hexdigest()
if p0digest != P0_SHA256:
    raise SystemExit(f'P0 override SHA mismatch: {p0digest} != {P0_SHA256}')

p1dir = root / '.p1-overrides-chunks'
p1parts = sorted(p1dir.glob('part-*.bin'))
if not p1parts:
    raise SystemExit('P1 override chunks not found')
p1raw = b''.join(p.read_bytes() for p in p1parts)
P1_BYTES = 12573
P1_SHA256 = '66ec55dd0571b8f13cbb57dc4841433253e5659c4834dbce693d28dbea88f7d2'
if len(p1raw) != P1_BYTES:
    raise SystemExit(f'P1 override size mismatch: {len(p1raw)} != {P1_BYTES}')
p1digest = hashlib.sha256(p1raw).hexdigest()
if p1digest != P1_SHA256:
    raise SystemExit(f'P1 override SHA mismatch: {p1digest} != {P1_SHA256}')

out = root / 'dist'
if out.exists():
    shutil.rmtree(out)
out.mkdir()
(out / 'index.html').write_text(html, encoding='utf-8')
(out / 'cloud-p1-overrides.js').write_bytes(p1raw)
(out / 'cloud-adapter.js').write_bytes((root / 'cloud-adapter.js').read_bytes())
(out / 'cloud-p0-overrides.js').write_bytes(p0raw)
print(f'Built verified CRM source: {TARGET_BYTES} bytes / {digest}; P0 override {P0_BYTES} bytes / {p0digest}; P1 override {P1_BYTES} bytes / {p1digest}')
