from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
adapter_path = dist / 'cloud-adapter.js'

P0_BYTES = 33997
P0_SHA256 = '96aebe67255397475092b794281d55375f709e74b549955ea57741600f90442f'
P1_BYTES = 12573
P1_SHA256 = '66ec55dd0571b8f13cbb57dc4841433253e5659c4834dbce693d28dbea88f7d2'
P1_ARCHIVE_BYTES = 2548
P1_ARCHIVE_SHA256 = '935a1002edf9fd7bf82851cd89806f33935ebe486372dfabf91a5bd15062742c'

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def require_asset(name, expected_bytes, expected_sha):
    path = dist / name
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if len(raw) != expected_bytes or digest != expected_sha:
        raise SystemExit(
            f'{name} integrity mismatch: {len(raw)} bytes / {digest}; '
            f'expected {expected_bytes} / {expected_sha}'
        )

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)

for name, size, digest in (
    ('cloud-p0-overrides.js', P0_BYTES, P0_SHA256),
    ('cloud-p1-overrides.js', P1_BYTES, P1_SHA256),
    ('cloud-p1-archive.js', P1_ARCHIVE_BYTES, P1_ARCHIVE_SHA256),
):
    require_asset(name, size, digest)

html = index_path.read_text(encoding='utf-8')

old_status = '<div class="bg-white border border-slate-200 rounded-2xl p-4"><div class="text-[11px] text-slate-400">合作状态</div><div class="mt-2"><span class="inline-flex px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700">合作中</span></div></div>'
new_status = '<div class="bg-white border border-slate-200 rounded-2xl p-4"><div class="text-[11px] text-slate-400">合作状态</div><div class="mt-2"><span class="inline-flex px-2.5 py-1 rounded-full text-xs font-bold" :class="selectedClient.archived?\'bg-slate-100 text-slate-600\':statusStyle(selectedClient.status)">{{ selectedClient.archived?\'已归档\':statusText(selectedClient.status) }}</span></div></div>'
html = replace_once(html, old_status, new_status, 'client detail hard-coded status')

html = replace_once(
    html,
    '本地存储容量 {{ storageUsageText }}',
    '浏览器本地缓存占用 {{ storageUsageText }}',
    'browser cache usage heading'
)
html = replace_once(
    html,
    '数据量已较大，建议立即导出备份，并尽快迁移到数据库。',
    '浏览器本地缓存占用较大，建议立即导出脱敏备份；业务主数据仍以云端为准。',
    'browser cache warning copy'
)
html = replace_once(
    html,
    '当前本地数据容量正常。自动快照仅保留最近 5 份，避免浏览器空间被占满。',
    '当前浏览器本地缓存占用正常；这里只统计此浏览器的 localStorage，不代表 Supabase 数据库或存储配额。',
    'browser cache normal copy'
)

# P2 billing rule A: in the contract's first month, an automatic service-fee
# invoice cannot be due before the contract start date. Later months keep the
# configured monthly due day unchanged.
html = replace_once(
    html,
    'dueDate:this.monthDueDate(month,client.renewalAlertDay),',
    "dueDate:(()=>{const scheduled=this.monthDueDate(month,client.renewalAlertDay),start=String(client.startDate||'').slice(0,10);return start&&month===start.slice(0,7)&&scheduled<start?start:scheduled})(),",
    'first-month automatic receivable due-date clamp'
)

script_order = (
    '<script src="/cloud-p1-overrides.js"></script>'
    '<script src="/cloud-p1-archive.js"></script>'
    '<script src="/cloud-adapter.js"></script>'
    '<script src="/cloud-p0-overrides.js"></script>'
)
if html.count(script_order) != 1:
    raise SystemExit('Unexpected production override script order')

index_path.write_text(html, encoding='utf-8')

adapter = adapter_path.read_text(encoding='utf-8')
old_login = """  vm.login=async()=>{try{const d=await rpc('crm_login',{p_username:String(vm.loginForm.username||'').trim(),p_password:String(vm.loginForm.password||'')});await enter(d);vm.logAudit('登录系统',`${vm.currentUser?.name||''} · ${vm.roleLabel(vm.currentUser?.role)}`);vm.persist();vm.notify('已连接 Supabase 云端数据');}catch(e){vm.notify(e?.message||'账号或密码错误');}};"""
new_login = """  vm.login=async()=>{try{const d=await rpc('crm_login',{p_username:String(vm.loginForm.username||'').trim(),p_password:String(vm.loginForm.password||'')});if(d?.error==='INVALID_CREDENTIALS'){vm.notify('账号或密码错误');return}if(d?.error){vm.notify('登录失败');return}await enter(d);vm.logAudit('登录系统',`${vm.currentUser?.name||''} · ${vm.roleLabel(vm.currentUser?.role)}`);vm.persist();vm.notify('已连接 Supabase 云端数据');}catch(e){vm.notify(String(e?.message||'').includes('INVALID_CREDENTIALS')?'账号或密码错误':(e?.message||'账号或密码错误'))}finally{vm.loginForm.password=''}};"""
adapter = replace_once(adapter, old_login, new_login, 'cloud login compatibility wrapper')
adapter_path.write_text(adapter, encoding='utf-8')

print(
    'P2_FINALIZE_OK: '
    f'index={sha256_bytes(index_path.read_bytes())}; '
    f'adapter={sha256_bytes(adapter_path.read_bytes())}'
)
