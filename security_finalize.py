from pathlib import Path
import hashlib, shutil

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
adapter_path = dist / 'cloud-adapter.js'
p1_overrides_path = dist / 'cloud-p1-overrides.js'
security_src = root / 'cloud-security-hotfix.js'
security_dst = dist / 'cloud-security-hotfix.js'

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if not security_src.exists():
    raise SystemExit('cloud-security-hotfix.js missing')
if not p1_overrides_path.exists():
    raise SystemExit('cloud-p1-overrides.js missing')

html = index_path.read_text(encoding='utf-8')
adapter = adapter_path.read_text(encoding='utf-8')
p1_overrides = p1_overrides_path.read_text(encoding='utf-8')

p0_tag = '<script src="/cloud-p0-overrides.js"></script>'
security_tag = '<script src="/cloud-security-hotfix.js"></script>'
if html.count(p0_tag) != 1:
    raise SystemExit('Unexpected P0 script tag count')
if security_tag in html:
    raise SystemExit('Security hotfix script tag already present before finalize')
html = html.replace(p0_tag, p0_tag + security_tag, 1)

adapter = replace_once(
    adapter,
    "rpc('crm_login'",
    "rpc('crm_login_v3'",
    'security v3 login endpoint'
)
adapter = replace_once(
    adapter,
    "rpc('crm_load_state'",
    "rpc('crm_load_state_v3'",
    'security v3 load endpoint'
)

p1_overrides = replace_once(
    p1_overrides,
    "const d=await cloud.rpc('crm_load_state',{p_token:token});",
    "const d=await cloud.rpc('crm_load_state_v3',{p_token:token});",
    'P1 conflict recovery v3 load endpoint'
)
p1_overrides = replace_once(
    p1_overrides,
    """if(state.active&&!state.localBackupExportedAt){
      notify(vm,'请先导出本地脱敏副本，确认保存后再重新载入云端最新版本');
      return false;
    }""",
    """if(state.active&&!state.localBackupExportedAt){
      const status=overlay?.querySelector?.('[data-p1-status]');
      if(status)status.textContent='请先点击“导出本地脱敏副本”，导出成功后再重新载入云端最新版本';
      notify(vm,'请先导出本地脱敏副本，确认保存后再重新载入云端最新版本');
      return false;
    }""",
    'P1 conflict recovery inline export guidance'
)

index_path.write_text(html, encoding='utf-8')
adapter_path.write_text(adapter, encoding='utf-8')
p1_overrides_path.write_text(p1_overrides, encoding='utf-8')
shutil.copyfile(security_src, security_dst)

print(
    'SECURITY_FINALIZE_OK: '
    f'index={sha(index_path)}; '
    f'adapter={sha(adapter_path)}; '
    f'p1={sha(p1_overrides_path)}; '
    f'security={sha(security_dst)}'
)
